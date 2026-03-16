# Technical Debt Roadmap

**Created:** March 13, 2026
**Status:** Planning
**Purpose:** Organize, refactor, and solidify the existing Autograder codebase into a cohesive, decoupled, and evolutionary architecture before adding new features.

---

## Context

The Autograder is a pipeline-based grading system where submissions flow through ordered steps: Load Template → Build Tree → Pre-Flight → Grade → Focus → Feedback → Export. Each step receives a `PipelineExecution` object, performs its operation, and passes results forward.

The system has grown organically with features like multi-language support, setup configs, focus-based feedback, and AI execution being added incrementally. This has introduced coupling, incomplete abstractions, and inconsistencies that need to be resolved before the architecture can evolve cleanly.

This roadmap does not propose new features. It focuses exclusively on making the existing code solid, well-separated, and aligned with the pipeline architecture that is already in place.

---

## Roadmap Items

### 🔴 Priority 1 — Broken or Incomplete Implementations

These items represent code that is actively broken, logically inverted, or fundamentally incomplete. They must be fixed before any other refactoring work because they affect correctness.

#### Item 1: Fix Inverted Reporter Mode Assignment in `ReporterService`

- **File:** `autograder/services/report/reporter_service.py`
- **Problem:** The constructor assigns the wrong reporter for each mode. When `feedback_mode == "ai"`, it instantiates `DefaultReporter()`. When the mode is anything else (including `"default"`), it instantiates `AiReporter()`. This is a logic inversion — the conditional is backwards.
- **Impact:** Any pipeline configured with `feedback_mode="ai"` silently gets the default reporter (which is a no-op `pass`), and any pipeline configured with `feedback_mode="default"` gets the AI reporter (which returns a hardcoded string). Neither path produces correct feedback.
- **Action:**
  - Swap the conditional: `"ai"` → `AiReporter()`, else → `DefaultReporter()`.
  - Add a `generate_feedback()` method to `ReporterService` that delegates to the internal reporter, since `FeedbackStep` calls `self._reporter_service.generate_feedback()` but no such method exists on `ReporterService` — only `generate_report()` exists on the reporters themselves.

#### Item 2: Implement the `DefaultReporter` (Currently a No-Op)

- **File:** `autograder/services/report/default_reporter.py`
- **Problem:** `DefaultReporter.generate_report()` is `pass` — it returns `None`. This means the entire default feedback path produces no output. The `FeedbackPreferences` dataclass defines a rich configuration model (`GeneralPreferences`, `DefaultReporterPreferences` with category headers, score visibility, summary toggles) but none of it is consumed anywhere.
- **Impact:** The `FeedbackStep` in the pipeline always produces `None` data for default mode, which means `GradingResult.feedback` is always `None` unless AI mode is used (and even that is broken per Item 1).
- **Action:**
  - Implement `DefaultReporter.generate_report()` to produce a structured text/markdown report using the `ResultTree`, `Focus` data, and `FeedbackPreferences`.
  - The report should use `ResultTreeFormatter` (which already exists and has methods like `format_test_results`, `format_failed_test_results`, `format_category`, etc.) as the rendering engine.
  - Consume the `DefaultReporterPreferences.category_headers` for section titles and `GeneralPreferences` flags for controlling what appears in the report.

#### Item 3: Remove Stale `test_library` Field from `CriteriaConfig`

- **File:** `autograder/models/config/criteria.py`
- **Problem:** `CriteriaConfig` has a `test_library: Optional[str]` field with a TODO comment saying "Remove this attribute (it already sits in grading config)." The template name is already passed separately to `build_pipeline()` and stored in the grading configuration at the web layer. This field is never read by any service — `CriteriaTreeService.build_tree()` receives the template as a separate argument.
- **Impact:** The field creates confusion about where the template name is authoritative. It also means criteria JSON files may include a `test_library` key that is silently ignored, misleading configuration authors.
- **Action:**
  - Remove the `test_library` field from `CriteriaConfig`.
  - Audit all criteria JSON files (e.g., `docs/criteria_example.json`, example configs) and remove any `test_library` keys.
  - Since the model uses `extra = "forbid"`, any existing JSON with this field will start failing validation — which is the correct behavior, as it forces cleanup.

#### Item 4: Fix `FeedbackStep` Contract Mismatch

- **File:** `autograder/steps/feedback_step.py`
- **Problem:** The step calls `self._reporter_service.generate_feedback(grading_result=focused_tests, feedback_config=self._feedback_config)`, but `ReporterService` has no `generate_feedback` method. The underlying reporters only have `generate_report(self, results)`. Additionally, the step does `return pipeline_exec.add_step_result(feedback)` assuming `feedback` is already a `StepResult`, but `generate_report` returns a string (or `None`). The step would crash at runtime.
- **Impact:** The feedback pipeline step cannot execute successfully in its current form.
- **Action:**
  - Add a `generate_feedback(grading_result, feedback_config)` method to `ReporterService` that parses the feedback config into `FeedbackPreferences`, passes the relevant data to the internal reporter, and returns the feedback string.
  - Fix the step to wrap the returned feedback string in a `StepResult(step=StepName.FEEDBACK, data=feedback_string, status=StepStatus.SUCCESS)`.

---

### 🟡 Priority 2 — Architectural Coupling & Separation of Concerns

These items address structural problems where components are tightly coupled, responsibilities are mixed, or abstractions are leaky. Fixing these makes the codebase easier to extend and test.

#### Item 5: Decouple Sandbox Lifecycle from `PreFlightStep`

- **Files:** `autograder/steps/pre_flight_step.py`, `autograder/services/pre_flight_service.py`, `autograder/autograder.py`
- **Problem:** The `PreFlightStep` currently has three distinct responsibilities: (1) validate required files, (2) execute setup commands, and (3) create and manage the sandbox container. Sandbox creation is an infrastructure concern that is conceptually separate from submission validation. The step stores the sandbox as its `StepResult.data`, which means downstream steps (`GradeStep`) must know to look inside the pre-flight result to find the sandbox. There's also a TODO comment in the step about when to destroy the sandbox on setup command failure.
- **Impact:** If a future step needs a sandbox but doesn't need pre-flight checks (e.g., a hypothetical "run student tests" step), there's no way to get a sandbox without going through pre-flight. The sandbox lifecycle is also split: creation happens in `PreFlightService`, but cleanup happens in `AutograderPipeline._cleanup_sandbox()`, which directly imports `sandbox_manager` and reaches into the pre-flight step result.
- **Action:**
  - Extract sandbox acquisition into a dedicated concern. Two approaches:
    - **Option A (Minimal):** Keep sandbox creation in `PreFlightService` but make `PipelineExecution` hold a first-class `sandbox` attribute (instead of hiding it in a step result's `data` field). The pipeline's `_cleanup_sandbox` would then read from `pipeline_execution.sandbox` directly.
    - **Option B (Full separation):** Create a `SandboxStep` that runs after pre-flight and before grading. It acquires the sandbox, prepares the workdir, and stores it on `PipelineExecution`. Pre-flight becomes purely about validation.
  - Regardless of approach, centralize the sandbox cleanup logic so it's not split between `AutograderPipeline._cleanup_sandbox()` and the implicit "don't destroy on failure" behavior in `PreFlightStep`.

#### Item 6: Decouple `GraderService` from Mutable State

- **File:** `autograder/services/grader_service.py`
- **Problem:** `GraderService` is instantiated once per `GradeStep` but accumulates mutable state through setter methods: `set_sandbox()`, `set_submission_language()`, and internal `__submission_files`. This makes the service stateful and order-dependent — callers must remember to call setters before `grade_from_tree()`. It also means the service cannot be safely reused across concurrent submissions.
- **Impact:** The setter pattern (`set_sandbox`, `set_submission_language`) is a code smell that indicates these values should be parameters, not instance state. It also creates a hidden coupling: `GradeStep.execute()` must know the exact sequence of setter calls before invoking grading.
- **Action:**
  - Refactor `grade_from_tree()` to accept `sandbox`, `submission_language`, and `submission_files` as explicit parameters instead of relying on pre-set instance state.
  - Remove the setter methods and the instance variables they populate.
  - `GraderService` becomes stateless and can be a singleton or module-level utility.

#### Item 7: Extract Language Resolution from Test Execution

- **Files:** `autograder/services/grader_service.py`, `autograder/template_library/input_output.py`, `autograder/services/command_resolver.py`
- **Problem:** The `GraderService.process_test()` method injects `__submission_language__` as a hidden parameter into every test's kwargs dict. The `ExpectOutputTest` and `DontFailTest` in `input_output.py` then extract this hidden parameter to resolve the `program_command` via `CommandResolver`. This creates an implicit contract: tests must know to look for a magic key in their kwargs, and the grader must know to inject it.
- **Impact:** The `__submission_language__` convention is undocumented, fragile, and invisible to anyone reading the `TestFunction.execute()` signature. It also means command resolution logic is scattered: `CommandResolver` lives in `services/`, but it's invoked inside individual test functions rather than at the pipeline level.
- **Action:**
  - Resolve commands at the `GradeStep` or `BuildTreeStep` level, before tests execute. When building `TestNode` objects, resolve any `program_command` parameter using `CommandResolver` and the submission's language. By the time a test executes, its parameters should contain the final, resolved command string.
  - Remove the `__submission_language__` injection from `GraderService.process_test()`.
  - This makes `TestFunction.execute()` a pure function of its declared parameters — no hidden state.

#### Item 8: Unify the Template Registration and Discovery System

- **Files:** `autograder/template_library/__init__.py`, `autograder/services/template_library_service.py`
- **Problem:** There are two parallel systems for template access:
  1. `TEMPLATE_REGISTRY` dict in `__init__.py` with `get_template()` and `get_template_instance()` module-level functions.
  2. `TemplateLibraryService` singleton that wraps the registry, caches instances, and adds metadata methods.
  The `TemplateLoaderStep` uses `TemplateLibraryService`, but the service internally calls `get_template_instance()` from the module. The web layer's `lifespan.py` also initializes `TemplateLibraryService` at startup. This creates a confusing dual-path where templates can be accessed through either system.
- **Impact:** Two entry points for the same data means two places to maintain, two places where bugs can hide, and confusion about which to use. The module-level functions also make testing harder (no way to inject mocks without patching globals).
- **Action:**
  - Make `TemplateLibraryService` the single authority for template access. Move the `TEMPLATE_REGISTRY` dict into the service class.
  - Remove the module-level `get_template()` and `get_template_instance()` functions, or make them thin wrappers that delegate to `TemplateLibraryService.get_instance()`.
  - Ensure all consumers (steps, web layer, GitHub action) go through the service.

#### Item 9: Formalize the `PipelineExecution` Data Flow Contract

- **File:** `autograder/models/pipeline_execution.py`
- **Problem:** `PipelineExecution` stores step results as a flat list of `StepResult` objects. Each step must know which previous step's data it needs and call `get_step_result(StepName.X).data` with the correct step name. The `data` field is typed as generic `T` but in practice is `Any` — it could be a `Template`, a `CriteriaTree`, a `SandboxContainer`, a `GradeStepResult`, a `Focus`, or a string. There's no compile-time or runtime validation that a step receives the data type it expects.
- **Impact:** Steps are coupled to each other's internal data shapes through implicit knowledge. If a step changes what it stores in `data`, downstream steps break silently. The `finish_execution()` method also hardcodes knowledge of which steps exist (`StepName.GRADE`, `StepName.FEEDBACK`, `StepName.FOCUS`) to assemble the final `GradingResult`.
- **Action:**
  - Add typed accessor properties to `PipelineExecution` for commonly accessed data: `template`, `criteria_tree`, `sandbox`, `grade_result`, `focus`, `feedback`. Each property internally calls `get_step_result()` and casts to the expected type.
  - This doesn't change the storage mechanism but provides a typed interface that makes the data flow explicit and catches mismatches earlier.
  - Refactor `finish_execution()` to use these typed accessors instead of raw `get_step_result()` calls.

---

### 🟢 Priority 3 — Code Quality & Consistency

These items address inconsistencies, dead code, and patterns that make the codebase harder to understand and maintain. They don't affect correctness but reduce cognitive load.

#### Item 10: Clean Up the `web_dev.py` Monolith (1422 Lines)

- **File:** `autograder/template_library/web_dev.py`
- **Problem:** This single file contains 36 test function classes plus the `WebDevTemplate` class, totaling 1422 lines. Each test class follows the same pattern (name, description, parameter_description, required_file, execute) but they're all in one file. There's also an inconsistent test registration key: `"Count Unused Css Classes"` uses spaces and title case while all others use `snake_case`.
- **Impact:** The file is difficult to navigate, review, and test in isolation. Adding a new web dev test means modifying a 1400-line file. The inconsistent key means test lookup behavior differs for that one test.
- **Action:**
  - Split into sub-modules: `template_library/web_dev/html_tests.py`, `template_library/web_dev/css_tests.py`, `template_library/web_dev/js_tests.py`, `template_library/web_dev/structure_tests.py`.
  - Keep `WebDevTemplate` in `template_library/web_dev/__init__.py` as the aggregator that imports and registers all tests.
  - Fix the `"Count Unused Css Classes"` key to `"count_unused_css_classes"` for consistency.

#### Item 11: Standardize Language Across the Codebase

- **Files:** Multiple files across `autograder/`, `web/`
- **Problem:** The codebase mixes Portuguese and English inconsistently:
  - Error messages: `"Erro: Arquivo ou diretório obrigatório não encontrado"` (Portuguese) in `PreFlightService`, but `"Error: Setup command failed"` (English) in the same file.
  - Test descriptions in `web_dev.py`: All in Portuguese (e.g., `"Verifica se o código JS usa um número mínimo de métodos comuns de manipulação do DOM."`).
  - `FeedbackPreferences` defaults: Portuguese category headers (`"✅ Requisitos Essenciais"`).
  - AI executor prompts: Portuguese (`"Você é um assistente de avaliação de código"`).
  - Logging and code comments: English.
- **Impact:** Contributors must context-switch between languages. Error messages shown to students are inconsistent. Internationalization becomes harder when strings are hardcoded in mixed languages.
- **Action:**
  - Decide on a language strategy: either (a) all internal code/logs in English with a separate i18n layer for student-facing strings, or (b) all student-facing strings in Portuguese with English internals.
  - Extract all hardcoded student-facing strings into a centralized location (e.g., a `messages.py` or locale file) so they can be managed and eventually translated.
  - This is a large task — start with the `PreFlightService` error messages and `FeedbackPreferences` defaults as the first pass.

#### Item 12: Remove Dead Code and Empty Modules

- **Files:** `autograder/services/parsers/__init__.py`, `autograder/models/dataclass/autograder_response.py`
- **Problem:**
  - `autograder/services/parsers/` is an empty package (only `__init__.py` with 0 lines). No code imports from it. It appears to be a leftover from a planned feature that was never implemented.
  - `AutograderResponse` dataclass has fields (`status`, `final_score`, `feedback`, `test_report`) that overlap with `GradingResult` but is not used anywhere in the pipeline. The pipeline produces `PipelineExecution` → `GradingResult`, never `AutograderResponse`. It may be a legacy model from before the pipeline architecture was introduced.
- **Impact:** Dead code creates confusion about what's active and what's legacy. New contributors may try to use these thinking they're part of the current architecture.
- **Action:**
  - Delete `autograder/services/parsers/` directory.
  - Verify `AutograderResponse` has no imports anywhere. If confirmed unused, delete it. If it's used in the GitHub Action path, consolidate it with `GradingResult`.

#### Item 13: Consolidate the `required_file` / `required_file_type` Naming

- **Files:** `autograder/models/abstract/test_function.py`, all template test classes
- **Problem:** The abstract `TestFunction` class defines `required_file_type` (returns a string like `"HTML"`, `"CSS"`, `"JavaScript"`), but every concrete test class implements a property called `required_file` (not `required_file_type`). The abstract property `required_file_type` has a default implementation returning `None`, so concrete classes don't override it — they define their own `required_file` property that is not part of the abstract contract.
- **Impact:** The `required_file` property on concrete tests is used by `TemplateLibraryService.get_template_info()` to list test metadata, but it's not enforced by the abstract class. A new test could omit it without any error. The naming mismatch (`required_file` vs `required_file_type`) also creates confusion about what the property represents.
- **Action:**
  - Decide on one name. Since the concrete implementations all use `required_file` and return descriptive strings like `"HTML"`, `"CSS"`, rename the abstract property from `required_file_type` to `required_file` and make it abstract (or keep the default `None` for tests that don't require files).
  - Update all concrete test classes to explicitly override the abstract property.

#### Item 14: Clean Up `print()` Statements in Production Code

- **Files:** `autograder/utils/executors/ai_executor.py`, `autograder/services/upstash_driver.py`, `autograder/services/template_library_service.py`
- **Problem:** Several files use `print()` for output instead of the logging framework:
  - `AiExecutor`: 8+ `print()` calls for debugging AI responses (`"Sending AI engine batch request..."`, `"Found matching TestResult for AI result:"`, etc.)
  - `UpstashDriver`: `print(f"User '{username}' created.")`, `print(f"Score '{score}' set...")`
  - `TemplateLibraryService._load_all_templates()`: `print(f"Warning: Failed to load template...")`
- **Impact:** `print()` output goes to stdout with no level, timestamp, or source information. It can't be filtered, routed, or suppressed in production. It also mixes with structured log output.
- **Action:**
  - Replace all `print()` calls with appropriate `logger.info()`, `logger.debug()`, or `logger.warning()` calls using the module's logger.

#### Item 15: Decouple `UpstashDriver` from Global Environment Loading

- **File:** `autograder/services/upstash_driver.py`
- **Problem:** The file calls `load_dotenv()` at module import time (line 6), outside any function or class. This means importing the module has the side effect of loading `.env` into the process environment. The TODO comment acknowledges this: "place this in application startup."
- **Impact:** Module-level side effects make testing unpredictable and can interfere with other modules' environment expectations. It also means the `.env` file is loaded even if `UpstashDriver` is never instantiated.
- **Action:**
  - Remove the module-level `load_dotenv()` call.
  - Ensure environment loading happens once at application startup (in `web/core/lifespan.py` or the GitHub Action's `main.py`).
  - Consider making `UpstashDriver.__init__()` accept the Redis URL and token as constructor parameters instead of reading from `os.getenv()` directly, enabling dependency injection and testability.


#### Item 16: Standardize the `Template` Abstract Class Contract

- **File:** `autograder/models/abstract/template.py`
- **Problem:** The `Template` ABC defines `get_test(name)` as abstract but `get_tests()` as a concrete method that accesses `self.tests` — an attribute that is not declared in the abstract class. Each concrete template (`WebDevTemplate`, `InputOutputTemplate`, `ApiTestingTemplate`) defines `self.tests` as a dict in `__init__`, but this is a convention, not a contract. The ABC also has properties like `requires_pre_executed_tree` and `execution_helper` that appear on some templates (`WebDevTemplate`, `ApiTestingTemplate`) but are not part of the abstract class.
- **Impact:** The abstract class doesn't fully describe what a template must provide. A new template author must read existing implementations to understand the implicit contract (must have `self.tests` dict, may need `requires_pre_executed_tree`, etc.).
- **Action:**
  - Add `tests: Dict[str, TestFunction]` as a declared attribute (or abstract property) on the `Template` ABC.
  - Either add `requires_pre_executed_tree` and `execution_helper` to the ABC with default implementations, or remove them from concrete templates if they're unused (they currently return `False` and `None` respectively and nothing reads them).
  - Audit all template properties to ensure the ABC is the single source of truth for the template contract.

---

### 🔵 Priority 4 — Evolutionary Architecture Preparation

These items prepare the codebase for future growth by establishing patterns and removing obstacles. They are not urgent but will pay dividends as the system scales.

#### Item 17: Introduce a Step Registry Pattern for Pipeline Construction

- **File:** `autograder/autograder.py`
- **Problem:** `build_pipeline()` is a 60-line function with conditional logic for each optional step (pre-flight, feedback, export). Adding a new step requires modifying this function, understanding the ordering constraints, and knowing which services to instantiate. The function also hardcodes service instantiation (e.g., `FocusService()`, `ReporterService(feedback_mode)`, `UpstashDriver`).
- **Impact:** Pipeline construction is monolithic. There's no way to compose pipelines from configuration or to add steps without touching the builder function.
- **Action:**
  - Create a `StepRegistry` that maps `StepName` to a factory function. Each factory receives the relevant config slice and returns a configured `Step` instance.
  - Refactor `build_pipeline()` to iterate over a list of desired step names and use the registry to instantiate them.
  - This makes it possible to define pipeline compositions declaratively (e.g., "this assignment uses steps: LOAD_TEMPLATE, BUILD_TREE, PRE_FLIGHT, GRADE, FOCUS, FEEDBACK") without modifying builder code.

#### Item 18: Formalize the Exporter as a Plugin Interface

- **Files:** `autograder/steps/export_step.py`, `autograder/services/upstash_driver.py`, `github_action/github_action_service.py`
- **Problem:** The `ExporterStep` receives an `exporter_service` but there's no abstract interface defining what an exporter must implement. `UpstashDriver` has `set_score()`, but the GitHub Action's `export_results()` has a completely different signature. The `build_pipeline()` function passes `UpstashDriver` (the class, not an instance) to `ExporterStep`, which means the step would need to instantiate it — but the step just calls `self._exporter_service.set_score()` directly, which would fail on a class reference.
- **Impact:** There's no way to swap exporters without modifying the step. The GitHub Action has its own export path (`GithubActionService.export_results()`) that bypasses the pipeline's export step entirely.
- **Action:**
  - Define an `Exporter` ABC with a `export(user_id, score, feedback)` method.
  - Make `UpstashDriver` implement this interface.
  - Create a `GithubClassroomExporter` that wraps the GitHub Action's export logic.
  - Fix `build_pipeline()` to pass an exporter instance (not a class reference).

#### Item 19: Separate the `PipelineExecution` Summary Logic from the Model

- **File:** `autograder/models/pipeline_execution.py`
- **Problem:** `PipelineExecution` is a data model (holds step results, submission, status) but also contains 100+ lines of presentation logic in `get_pipeline_execution_summary()` and `_extract_error_details()`. The `_extract_error_details` method parses error message strings using string matching (`"Arquivo ou diretório obrigatório não encontrado" in error_text`, `"Setup command" in error_text`) to reconstruct structured data that was originally structured in `PreFlightService` but was flattened into a string by `PreFlightStep._format_errors()`.
- **Impact:** The model is doing serialization, presentation, and reverse-parsing of its own error strings. This is fragile — if error message wording changes, the parser breaks. It also means the model knows about the internal format of every step's errors.
- **Action:**
  - Store `PreflightError` objects (or their dicts) directly in the step result instead of formatting them into a string and then parsing the string back. The `PreFlightStep` should store structured error data, and the summary generator should read it directly.
  - Extract `get_pipeline_execution_summary()` into a separate `PipelineExecutionSerializer` or utility function that takes a `PipelineExecution` and produces the API-facing dict. This keeps the model clean and the serialization logic testable independently.

#### Item 20: Establish a Consistent Error Handling Strategy Across Steps

- **Files:** All files in `autograder/steps/`
- **Problem:** Each step handles errors differently:
  - `TemplateLoaderStep`: Catches all exceptions, returns `StepResult` with `FAIL` status and error string.
  - `BuildTreeStep`: Same pattern but also passes `original_input=pipeline_exec`.
  - `PreFlightStep`: Returns `FAIL` with formatted error string, but also has inline comments questioning error handling (`"Needs error handling?"`, `"Return Sandbox Here anyway?"`, `"How to deal with sandbox destruction"`).
  - `GradeStep`: Catches all exceptions, returns `FAIL`.
  - `FocusStep`: Catches all exceptions, returns `FAIL`.
  - `FeedbackStep`: Catches all exceptions, returns `FAIL`.
  - `ExporterStep`: Catches all exceptions, returns `FAIL`.
  The `original_input` field is set inconsistently — some steps set it, others don't. The pipeline's `run()` method also catches exceptions separately and sets `INTERRUPTED` status, creating a dual error-handling path.
- **Impact:** Error handling is duplicated in every step with slight variations. The `original_input` field on `StepResult` is sometimes set and sometimes not, making it unreliable. The dual error path (step-level catch vs pipeline-level catch) means some errors are `FAIL` and others are `INTERRUPTED` with no clear semantic distinction.
- **Action:**
  - Create a base step class or decorator that wraps `execute()` in a standard try/except, constructs the `StepResult` with `FAIL` status, and logs the error. Individual steps only implement the happy path.
  - Decide on the semantics of `FAIL` vs `INTERRUPTED`: `FAIL` = step detected a known error condition (e.g., missing file), `INTERRUPTED` = unexpected exception. Document this.
  - Remove `original_input` from `StepResult` if it's not consistently used, or make it mandatory.

#### Item 21: Decouple the `AiExecutor` Batch Pattern from Test Execution

- **Files:** `autograder/utils/executors/ai_executor.py`, `autograder/services/grader_service.py`
- **Problem:** The `AiExecutor` implements a batch-send pattern where individual tests call `executor.add_test()` during tree traversal, and then `GraderService.grade_from_tree()` calls `executor.stop()` after all tests are processed to send a single batch request to OpenAI. This means:
  1. `GraderService` must know about `AiExecutor` and check for it after grading (`if hasattr(test_func, "executor") and test_func.executor`).
  2. Test functions that use AI don't actually execute during `execute()` — they register themselves and return an empty `TestResult` that gets populated later via `mapback()`.
  3. The executor stores mutable state (`tests`, `test_result_references`, `submission_files`) and mutates `TestResult` objects in place after the fact.
- **Impact:** This breaks the pipeline's mental model where each test executes and returns a result. Instead, AI tests return placeholder results that are silently mutated later. The `GraderService` has to know about this special case, creating coupling between the grading service and the AI execution strategy.
- **Action:**
  - Refactor AI execution into a pipeline-aware pattern. Options:
    - **Option A:** Make AI execution a post-processing step that runs after the grade step. The grade step marks AI tests as "pending," and a new `AiExecutionStep` collects them, sends the batch, and fills in the results.
    - **Option B:** Make the `AiExecutor` a strategy that the `GradeStep` can invoke after tree traversal, removing the need for `GraderService` to know about it.
  - Either way, eliminate the in-place mutation of `TestResult` objects and the `hasattr` check in `GraderService`.

---

## Progress Tracking

| # | Item | Priority | Status |
|---|------|----------|--------|
| 1 | Fix inverted reporter mode | 🔴 P1 | ⬜ To Do |
| 2 | Implement DefaultReporter | 🔴 P1 | ⬜ To Do |
| 3 | Remove stale test_library field | 🔴 P1 | ⬜ To Do |
| 4 | Fix FeedbackStep contract | 🔴 P1 | ⬜ To Do |
| 5 | Decouple sandbox from pre-flight | 🟡 P2 | ⬜ To Do |
| 6 | Decouple GraderService state | 🟡 P2 | ⬜ To Do |
| 7 | Extract language resolution | 🟡 P2 | ✅ Done |
| 8 | Unify template registration | 🟡 P2 | ⬜ To Do |
| 9 | Formalize PipelineExecution data flow | 🟡 P2 | ⬜ To Do |
| 10 | Split web_dev.py monolith | 🟢 P3 | ⬜ To Do |
| 11 | Standardize language (i18n) | 🟢 P3 | ⬜ To Do |
| 12 | Remove dead code | 🟢 P3 | ⬜ To Do |
| 13 | Consolidate required_file naming | 🟢 P3 | ⬜ To Do |
| 14 | Replace print() with logging | 🟢 P3 | ⬜ To Do |
| 15 | Decouple UpstashDriver env loading | 🟢 P3 | ⬜ To Do |
| 16 | Standardize Template ABC | 🟢 P3 | ⬜ To Do |
| 17 | Step registry pattern | 🔵 P4 | ⬜ To Do |
| 18 | Formalize exporter plugin | 🔵 P4 | ⬜ To Do |
| 19 | Separate summary from model | 🔵 P4 | ⬜ To Do |
| 20 | Consistent error handling | 🔵 P4 | ⬜ To Do |
| 21 | Decouple AiExecutor batch | 🔵 P4 | ⬜ To Do |

---

## Recommended Execution Order

The items have dependency relationships. Here is the suggested execution sequence:

**Phase 1 — Fix What's Broken (Items 1–4)**
These can be done in parallel. They fix code that would crash or produce wrong results at runtime.

**Phase 2 — Structural Decoupling (Items 5–9)**
Start with Item 6 (GraderService state) and Item 7 (language resolution) as they're self-contained. Then Item 5 (sandbox lifecycle) which touches more files. Items 8 and 9 can be done in parallel.

**Phase 3 — Code Quality (Items 10–16)**
These are independent of each other and can be tackled in any order. Item 10 (web_dev split) is the largest. Item 14 (print cleanup) is the quickest win.

**Phase 4 — Architecture Evolution (Items 17–21)**
Item 19 (summary separation) should come before Item 20 (error handling) since the error handling strategy depends on how errors are stored. Item 17 (step registry) enables Item 18 (exporter plugin). Item 21 (AiExecutor) is independent.
