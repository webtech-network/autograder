# Autograder — Agent & Contributor Reference

This document is the authoritative architectural reference for anyone working on this codebase — human or AI agent. Read it before making any change. Every design decision described here is intentional and must be respected.

---

## What this project is

The autograder is a **general-purpose code grading engine**. It accepts a submission (a set of files) and an assignment configuration (a grading criteria definition), runs a configurable pipeline of evaluation steps, and returns a score from 0 to 100 together with a structured result tree and optional feedback.

The core engine is deliberately domain-agnostic. It has no knowledge of GitHub, git, gamification, learning management systems, or any specific use case. Those concerns belong in the layers that sit on top of the core.

---

## Repository layout

```
autograder/          Core grading engine — the only thing that must stay general
sandbox_manager/     Infrastructure: Docker-based sandbox container management
github_action/       Adapter: runs the grader inside a GitHub Actions workflow
web/                 Adapter: FastAPI server exposing the grader as an HTTP API
tests/               Unit, integration, e2e, and web tests
```

The boundary between `autograder/` and everything else is the most important architectural line in the codebase. Code inside `autograder/` must not import from `web/`, `github_action/`, or any other adapter. The adapters import from `autograder/`, not the other way around.

---

## The two inputs: Submission and Assignment Configuration

Every grading execution starts with two independent inputs.

### Submission

A `Submission` (`autograder/models/dataclass/submission.py`) represents what is being evaluated. It carries:

- `submission_files: Dict[str, SubmissionFile]` — the files to grade, keyed by filename. Each `SubmissionFile` holds a `filename` and the full text `content`.
- `user_id` / `username` — identifiers for the submitter, used for logging and export. The autograder does not interpret or validate these values.
- `assignment_id` — an opaque identifier that links this submission to a grading configuration. The autograder treats this as a correlation ID only.
- `language: Optional[Language]` — the programming language of the submission. Required by any step that does language-specific analysis (AST parsing, sandbox execution).
- `locale: str` — controls the language of generated feedback messages.

The autograder does not fetch files, call APIs, or talk to version control. The caller constructs the `Submission` object with whatever files are relevant and passes it to the pipeline. Responsibility for understanding what files to include, and from where, belongs entirely to the caller.

### Assignment Configuration (Grading Config)

The assignment configuration is a set of JSON/dict structures passed to `build_pipeline()`:

- `template_name` — selects which `Template` (test library) to use.
- `grading_criteria` — a `CriteriaConfig` dict that defines the full scoring rubric: categories, subjects, tests, and weights. This is the central configuration artifact.
- `feedback_config` — preferences for the feedback report generator.
- `setup_config` — optional pre-flight instructions (required files, setup commands, assets to inject into the sandbox).

The criteria config is what separates one assignment from another. Two assignments using the same template can have completely different rubrics, weights, and test selections. The template provides the available test functions; the criteria config decides which ones to use and how to weight them.

---

## The Criteria Tree: the pluggable scoring engine

The criteria tree is the most important concept in the codebase. Understanding it fully is required to work anywhere in `autograder/`.

### What it is

A `CriteriaTree` (`autograder/models/criteria_tree.py`) is the compiled, in-memory representation of a grading rubric. It is built from the `grading_criteria` dict during `BuildTreeStep` and is immutable for the duration of a pipeline execution.

The tree has a fixed three-level top structure:

```
CriteriaTree
  ├── base: CategoryNode        (required — the main score, 0-100)
  ├── bonus: CategoryNode       (optional — adds points)
  └── penalty: CategoryNode     (optional — subtracts points)
```

Each `CategoryNode` can contain either:
- A flat list of `TestNode`s (leaves), or
- A list of `SubjectNode`s, each of which can recursively contain more subjects or tests.

This recursive subject structure allows arbitrary grouping and weighting of tests. A `SubjectNode` is just a weighted container — it has a `name`, a `weight`, and children that are either more subjects or test leaves.

### TestNode: the leaf

A `TestNode` is the leaf of the criteria tree. It holds:

- `test_function: TestFunction` — a reference to the actual callable that will evaluate the submission.
- `parameters: Dict[str, Any]` — the arguments that will be passed to the test function when it runs.
- `file_target: Optional[List[str]]` — if set, only these specific files from the submission will be passed to the test function.
- `weight: float` — the relative weight of this test within its parent subject.

The `TestNode` is what makes the criteria tree pluggable. The tree itself is generic — it has no knowledge of what any test does. The `test_function` field is the only concrete piece, and it can be any class that implements the `TestFunction` contract.

### The TestFunction contract

`TestFunction` (`autograder/models/abstract/test_function.py`) is an abstract base class. Every evaluator in the system — whether it checks HTML structure, runs code against expected output, detects forbidden imports, or calls an AI model — implements this single interface:

```python
def execute(
    self,
    files: Optional[List[SubmissionFile]],
    sandbox: Optional[SandboxContainer],
    *args,
    **kwargs
) -> TestResult:
```

The method receives:
- `files` — the submission files relevant to this test (filtered by `file_target`).
- `sandbox` — a live Docker container, if one was provisioned for this execution. May be `None` for tests that don't need execution.
- `**kwargs` — any test parameters from the `TestNode`, plus pipeline-injected context: `locale`, `structural_analysis`, `submission_language`, and `pre_computed_results`. Test functions that don't need a kwarg simply ignore it.

The return value is a `TestResult` with a `score` (0–100), a `report` string, and optional parameters. That is the entire contract.

This design is the source of the system's extensibility. Adding a new kind of evaluation — regex pattern matching, cyclomatic complexity measurement, external API calls — means writing a class that implements `execute()`. No changes to the pipeline, no changes to the criteria tree, no changes to the scoring logic.

### The Template: a named registry of TestFunctions

A `Template` (`autograder/models/abstract/template.py`) is a named collection of `TestFunction` instances, addressable by string key. It is the bridge between a criteria config (which references tests by name) and the actual test implementations.

```python
class StaticAnalysisTemplate(Template):
    def __init__(self):
        self.tests = {
            "forbidden_import": ForbiddenImportTest(),
            "forbidden_keyword": ForbiddenKeywordTest(),
            "ai_sorting_algorithm": AiSortingAlgorithmTest(),
        }
```

When `BuildTreeStep` processes a criteria config entry like `{ "type": "forbidden_import", ... }`, it looks up `"forbidden_import"` in the loaded template's registry and embeds that `TestFunction` instance directly into the `TestNode`. By the time the criteria tree is built, every leaf already holds a resolved, callable test function.

A template also declares `requires_sandbox: bool`, which tells the pipeline whether to provision a Docker container before grading begins.

Built-in templates live in `autograder/template_library/`. Custom templates can be passed directly to `build_pipeline()` without registration.

### Scoring: how weights propagate

Each node in the result tree (`ResultTree`) mirrors the criteria tree structure but holds computed scores. After all test functions execute, scores propagate bottom-up:

1. Each `TestResultNode` holds its raw score (0–100) as returned by `execute()`.
2. Each `SubjectResultNode` computes its score as a weighted average of its children's scores. Weights are normalised by `SubmissionGrader.__balance_nodes()` so sibling weights don't need to sum to any particular value — only their ratios matter.
3. Each `CategoryResultNode` does the same for its subjects.
4. `RootResultNode.calculate_score()` combines the three categories:
   - `final_score = base_score + (bonus_score / 100 * bonus_weight) - ((100 - penalty_score) / 100 * penalty_weight)`
   - The result is clamped to [0, 100].

This means a rubric author can freely assign arbitrary weights to tests and subjects without needing them to sum to 100. The engine normalises them automatically.

---

## The Pipeline: establishing resources and processing results

`AutograderPipeline` (`autograder/autograder.py`) is a linear chain of `Step` instances that share a single mutable `PipelineExecution` object. Each step receives the execution context, does its work, appends a `StepResult`, and returns the (possibly enriched) context to the next step.

The pipeline serves two purposes: **establishing resources** that test functions need to run (templates, AST roots, sandbox containers), and **post-processing** the result tree after grading.

### The fixed execution order

```
LoadTemplateStep        — load Template instances from the registry
BuildTreeStep           — compile criteria config → CriteriaTree with embedded TestFunctions
SandboxStep             — provision Docker container (skipped if no template requires_sandbox)
PreFlightStep           — check required files, inject assets, run setup commands (skipped if no setup_config)
AiBatchStep             — batch all AI-backed tests into a single API call (skipped if no AI tests)
StructuralAnalysisStep  — parse submission files into ast-grep AST roots
GradeStep               — traverse CriteriaTree, execute all TestFunctions, build ResultTree
FocusStep               — identify highest-impact failing tests for feedback prioritisation
FeedbackStep            — generate human-readable feedback report (skipped if include_feedback=False)
ExporterStep            — send results to an external system (skipped if export_results=False)
```

### Step conditionality

Steps are not always present. `StepRegistry` (`autograder/steps/step_registry.py`) acts as a factory: it inspects the pipeline configuration and the loaded templates, and returns `None` for steps that are not needed. Only non-`None` steps are added to the pipeline. This means `pipeline.run()` only executes the steps required for the specific assignment.

For example:
- `SandboxStep` is only built if at least one loaded template declares `requires_sandbox = True`.
- `PreFlightStep` is only built if `setup_config` is non-empty.
- `AiBatchStep` is only built if at least one `TestFunction` in the template is an `AiTestFunction`.
- `FeedbackStep` is only built if `include_feedback=True`.
- `ExporterStep` is only built if `export_results=True`.

### PipelineExecution: the shared context

`PipelineExecution` is the object that travels through every step. It holds:
- The original `Submission`
- A list of `StepResult` objects — one per executed step, in order
- The live `SandboxContainer` reference (set by `SandboxStep`, cleaned up after the pipeline finishes)
- The final `GradingResult` (set by `finish_execution()` after all steps complete)

Steps communicate with each other exclusively through `PipelineExecution`. A step that needs data produced by an earlier step calls a typed accessor like `pipeline_exec.get_built_criteria_tree()` or `pipeline_exec.get_structural_analysis_result()`. This makes the data flow explicit and auditable.

If any step produces a `StepResult` with `is_successful = False`, the pipeline halts immediately. No subsequent steps run. The `GradingResult` is `None` in this case.

### The role of pre-execution steps

`AiBatchStep` and `StructuralAnalysisStep` are pre-execution steps — they run before `GradeStep` and deposit their results into `PipelineExecution` for `GradeStep` to retrieve and pass to test functions.

`AiBatchStep` collects every `AiTestFunction` from the criteria tree, calls `build_prompt()` on each, batches all prompts into a single AI API call, and stores the results as `Dict[test_name, TestResult]`. When `GradeStep` later calls `execute()` on each `AiTestFunction`, it passes the pre-computed results as a `pre_computed_results` kwarg. The test function returns the pre-computed result directly, making zero additional API calls.

`StructuralAnalysisStep` parses every submission file into an `ast-grep` `SgRoot` AST object and stores the map `Dict[filename, SgRoot]` as a `StructuralAnalysisResult`. Test functions that do structural pattern matching (like `ForbiddenKeywordTest`) receive this via the `structural_analysis` kwarg.

This pattern — pre-compute an expensive resource once, inject it via kwargs — is how any new pipeline-level infrastructure should be introduced.

### Post-grading steps

`FocusStep` runs after `GradeStep`. It traverses the completed `ResultTree`, computes a `diff_score` for each failing test (how many points it cost, accounting for the full weight propagation path), and returns an ordered `Focus` object that surfaces the highest-impact failures. This drives feedback prioritisation.

`FeedbackStep` uses `Focus` and the `ResultTree` to generate a human-readable markdown report.

`ExporterStep` calls `exporter.export_with_context(pipeline_execution)` on whatever `Exporter` implementation was registered. The `Exporter` abstract class (`autograder/models/abstract/exporter.py`) is the extension point for pushing results to external systems.

---

## Infrastructure awareness: what the core knows vs. what it doesn't

The `autograder/` package is deliberately infrastructure-naive. It defines interfaces and expects implementations to be injected from outside. Specifically:

**What `autograder/` knows:**
- That a `SandboxContainer` exists and has methods like `run_command()` and `prepare_workdir()`. It does not know or care that this is a Docker container.
- That an `Exporter` exists with an `export()` / `export_with_context()` method. It does not know where results go.
- That an `AiExecutor` exists that takes prompts and returns scores. It does not know the model, provider, or API.

**What `autograder/` does not know:**
- How sandboxes are created, pooled, or destroyed. That is `sandbox_manager/`.
- How submissions arrive (HTTP request, GitHub Actions env vars, CLI). That is `web/` or `github_action/`.
- Where results are stored or reported. That is the `Exporter` implementation provided by the caller.
- Anything about git, GitHub, repositories, commits, or diffs.

### The sandbox_manager layer

`sandbox_manager/` manages pools of Docker containers. It exposes a `SandboxManager` with `get_sandbox(language)` and `release_sandbox(language, sandbox)`. The pipeline calls `get_sandbox()` during `SandboxStep` and `destroy_sandbox()` during cleanup — it never creates or destroys containers directly.

Containers run with `network_mode="none"`, `cap_drop=["ALL"]`, and a memory limit of 128MB. They are destroyed after every grading execution — never reused across submissions. The pool replenishes proactively to maintain a minimum number of idle containers.

A remote mode is also supported (`RemoteSandboxManager`) which forwards sandbox operations to a separate sandbox API server over HTTP, decoupling the autograder process from Docker.

### The web/ adapter

`web/` is a FastAPI application that exposes the autograder as an HTTP API. Its key responsibilities are:

- Accepting `SubmissionCreate` requests over HTTP.
- Loading the grading configuration from a PostgreSQL database (`GradingConfiguration`).
- Constructing a `Submission` object from the HTTP payload and calling `build_pipeline()` then `pipeline.run()`.
- Running grading as a background `asyncio` task (using `asyncio.to_thread` because the pipeline is synchronous).
- Persisting `SubmissionResult` to the database.

The web layer is the only place where persistence, HTTP, and database concerns live. The core engine has no database dependency.

### The github_action/ adapter

`github_action/` is a Docker-based GitHub Actions action. Its responsibilities:

- Reading configuration from environment variables injected by the Actions runtime.
- Walking `$GITHUB_WORKSPACE/submission/` to collect all submission files.
- Loading the grading criteria either from JSON files inside the repository (`.github/autograder/criteria.json`) or by fetching from the Autograder Cloud API.
- Calling `build_pipeline()` and `pipeline.run()`.
- Reporting the final score back to GitHub Classroom by updating the check run via the GitHub API.
- Committing a feedback markdown file to the repository if feedback is enabled.

The GitHub Action uses the same `build_pipeline()` / `pipeline.run()` interface as the web adapter. The core engine is unaware of which adapter is running it.

---

## Generality rule

This is the single most important constraint for contributors and agents:

**The `autograder/` package must never encode domain-specific, infrastructure-specific, or platform-specific concepts.**

In practice this means:

- No git vocabulary (`commit`, `branch`, `diff`, `repo`) in any file under `autograder/`.
- No GitHub, database, HTTP, or cloud references in any file under `autograder/`.
- New pipeline resources (analogous to `structural_analysis` or `pre_computed_results`) are introduced as optional, `None`-defaulting kwargs threaded through `SubmissionGrader.process_test()`. Test functions that need them read them; test functions that don't ignore them.
- Domain-specific context (e.g. which files changed in a contribution, raw diff hunks) belongs in open-ended `metadata` fields on `SubmissionFile` or `Submission`, not in new typed fields on core models. The exception is data that the pipeline itself must read and act on — those get typed fields with `Optional` and `None` defaults.
- Adding a new evaluation capability means writing a `TestFunction` subclass and registering it in a `Template`. It does not mean modifying the pipeline steps.

---

## Adding a new test function: the correct pattern

1. Create a class that extends `TestFunction` (or `AiTestFunction` for AI-backed tests).
2. Implement `name`, `description`, `parameter_description`, and `execute()`.
3. If the test needs a Pydantic config schema for parameter validation, implement `config_schema`.
4. Register the instance in a `Template`'s `tests` dict under a string key.
5. Reference that key as `type` in a `TestConfig` within the criteria config JSON.

No pipeline changes are needed. No step changes are needed. The test will be discovered by `BuildTreeStep`, embedded in the criteria tree, and executed by `GradeStep` automatically.

---

## Key data flow summary

```
Caller constructs Submission + passes grading_criteria dict
        │
        ▼
build_pipeline(template_name, grading_criteria, ...)
        │  StepRegistry inspects config + templates
        │  Only required steps are added
        ▼
AutograderPipeline.run(submission)
        │
        ├── LoadTemplateStep    → Template (test function registry)
        ├── BuildTreeStep       → CriteriaTree (TestNodes with embedded TestFunctions)
        ├── SandboxStep*        → SandboxContainer in PipelineExecution
        ├── PreFlightStep*      → validates files, injects assets, runs setup commands
        ├── AiBatchStep*        → Dict[test_name, TestResult] (pre-computed AI scores)
        ├── StructuralAnalysisStep → Dict[filename, SgRoot] (AST roots)
        ├── GradeStep           → ResultTree (scores for every test/subject/category)
        │       │
        │       └── SubmissionGrader.process_category/subject/test()
        │               └── TestFunction.execute(files, sandbox, **kwargs)
        │                       └── returns TestResult(score, report)
        ├── FocusStep           → Focus (highest-impact failing tests, sorted)
        ├── FeedbackStep*       → str (markdown feedback report)
        └── ExporterStep*       → calls Exporter.export_with_context()
                │
                ▼
        PipelineExecution.finish_execution()
                │
                ▼
        GradingResult(final_score, result_tree, feedback, focus)
```

Steps marked `*` are conditionally included based on configuration.
