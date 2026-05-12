# Product Vision Roadmap: Next-Generation Features

**Created:** May 12, 2026  
**Status:** RFC (Request for Comments)  
**Author:** Product Architecture Team  
**Purpose:** Conceptualize next-generation features that elevate the Autograder from a grading pipeline into a state-of-the-art intelligent educational engine.

---

## Executive Summary

The Autograder is a well-architected, pipeline-based grading engine with a clean extension model: abstract `Step` classes for pipeline stages, abstract `TestFunction`/`AiTestFunction` for grading logic, and `Template` classes for domain-specific test libraries. The system already supports Docker-based sandboxing, AI-batched evaluation, structural AST analysis, and multi-language execution.

This document proposes **10 high-impact features** across 5 dimensions that will transform this engine from a grading pipeline into an **intelligent educational platform**.

---

## 1. New Templates (`template_library/`)

### RFC 1.1: DataScienceTemplate — Jupyter & Pandas Validation

**Feature Name:** DataScienceTemplate  
**Target Persona:** Professor (Data Science / ML courses), Student (data science track)

**The Concept:**  
A template that grades data science assignments by executing Jupyter notebooks headlessly, validating DataFrame shapes, column types, statistical properties of outputs, and visualization correctness. Instead of just "does the code run?", it answers "did the student perform the correct data transformations and produce statistically valid results?"

**Technical Implementation:**
- New file: `autograder/template_library/data_science.py`
- New `TestFunction` subclasses:
  - `NotebookExecutionTest` — Executes `.ipynb` via `nbconvert`/`papermill` inside the sandbox, captures cell outputs
  - `DataFrameSchemaTest` — Validates output CSVs/DataFrames against expected schemas (column names, dtypes, row count ranges)
  - `StatisticalAssertionTest` — Checks that computed values (mean, std, correlation) fall within tolerance bands
  - `VisualizationExistsTest` — Verifies that matplotlib/seaborn plots were generated (checks for `.png` artifacts in sandbox)
- New sandbox image: `sandbox_manager/images/Dockerfile.python-ds` (adds pandas, numpy, matplotlib, scikit-learn, papermill)
- Register in `template_library/__init__.py`
- The template sets `requires_sandbox = True` and leverages `SandboxContainer.extract_file()` to pull generated artifacts for validation

**Challenges:**
- Notebook execution is non-deterministic (random seeds, floating-point drift) — requires tolerance-based assertions
- Large dependency footprint increases sandbox image size (~2GB) and cold-start time
- Students may use different library versions; need pinned environment specs per assignment

---

### RFC 1.2: SQLValidationTemplate — Database Query Grading

**Feature Name:** SQLValidationTemplate  
**Target Persona:** Professor (Database courses), Student (SQL/data engineering track)

**The Concept:**  
A template that spins up a pre-seeded database inside the sandbox, executes student SQL queries against it, and validates results against expected result sets — supporting partial credit for correct structure but wrong data, correct joins but missing filters, etc.

**Technical Implementation:**
- New file: `autograder/template_library/sql_validation.py`
- New `TestFunction` subclasses:
  - `QueryResultTest` — Executes student SQL, compares result set against expected (order-insensitive by default)
  - `QueryPlanAnalysisTest` — Runs `EXPLAIN` and checks for index usage, join types (rewards efficient queries)
  - `SchemaCreationTest` — Validates DDL output (table structure, constraints, foreign keys)
- New sandbox image: `sandbox_manager/images/Dockerfile.sql` (PostgreSQL + seed script injection via `ResolvedAsset`)
- Leverages existing `assets/s3_provider.py` to inject seed SQL files as `ResolvedAsset` during `PreFlightStep`
- Partial credit logic: 100% for exact match, 70% for correct columns/wrong rows, 40% for correct structure/wrong data

**Challenges:**
- Non-deterministic ordering requires set-based comparison (not string equality)
- Students may write valid but semantically different queries (multiple correct answers) — need configurable equivalence modes
- Database startup adds 2-3s latency per sandbox; mitigated by pre-warming pools in `LanguagePool`

---

## 2. New Pipeline Steps (`autograder/steps/`)

### RFC 2.1: PlagiarismDetectionStep — AST-Based Collusion Detection

**Feature Name:** PlagiarismDetectionStep  
**Target Persona:** Professor, Platform Admin (academic integrity)

**The Concept:**  
A pipeline step that runs *after* `StructuralAnalysisStep` and *before* `GradeStep`. It leverages the already-parsed AST roots (from `ast-grep`) to compute structural fingerprints of student code, then compares them against a corpus of previous submissions for the same assignment. Detects code cloning even when variable names are changed, whitespace is altered, or statements are reordered.

**Technical Implementation:**
- New file: `autograder/steps/plagiarism_step.py` — extends `Step` ABC
- New `StepName.PLAGIARISM` added to `StepName` enum in `models/dataclass/step_result.py`
- Register in `StepRegistry._builders` with conditional activation (config flag `enable_plagiarism_check`)
- Algorithm:
  1. Consume `StructuralAnalysisResult.roots` from previous step
  2. Walk each AST, extract normalized subtree hashes (winnowing algorithm / k-gram fingerprinting)
  3. Compare fingerprints against a Redis-backed corpus (reuse existing `UpstashDriver`)
  4. Store current submission's fingerprints for future comparisons
  5. Output: similarity score + matched submission IDs
- Result stored in `StepResult.data` as `PlagiarismResult(similarity_score, matched_submissions, flagged: bool)`
- `GradeStep` can optionally zero-out scores if `flagged=True` (configurable policy)

**Challenges:**
- Requires a persistent corpus across submissions — introduces statefulness into an otherwise stateless pipeline
- False positives on boilerplate/starter code — need configurable exclusion patterns (template code fingerprints)
- Cross-language plagiarism (e.g., Python → Java translation) requires IR-level comparison, significantly harder
- Privacy/FERPA concerns around storing student code fingerprints — needs data retention policies

---

### RFC 2.2: ComplexityProfilingStep — Empirical Big-O Analysis

**Feature Name:** ComplexityProfilingStep  
**Target Persona:** Professor (Algorithms & Data Structures courses), Student (performance awareness)

**The Concept:**  
A step that empirically measures the time/space complexity of student code by running it against progressively larger inputs inside the sandbox, fitting the execution time curve to known complexity classes (O(1), O(n), O(n log n), O(n²), O(2ⁿ)), and reporting whether the student's implementation meets the expected complexity bound.

**Technical Implementation:**
- New file: `autograder/steps/complexity_profiling_step.py` — extends `Step`
- New `StepName.COMPLEXITY_PROFILING` in the enum
- Runs *after* `SandboxStep` (needs a live sandbox) and *before* `GradeStep`
- Algorithm:
  1. Read `complexity_config` from assignment config (expected complexity class, input generator function, size progression)
  2. Generate inputs of sizes [10, 100, 1000, 10000, ...] using a configurable generator
  3. Execute student code in sandbox via `SandboxContainer.run_command()` with timing
  4. Fit execution times to complexity curves using least-squares regression
  5. Classify best-fit curve and compare against expected
- Output: `ComplexityResult(measured_class="O(n²)", expected_class="O(n log n)", passed=False, data_points=[...])`
- `GradeStep` can use this as a test result via `pre_computed_results` pattern (same as AI batch)

**Challenges:**
- Noisy measurements on small inputs — need statistical averaging (multiple runs per size)
- Container overhead adds constant-time noise — need to subtract baseline
- Some algorithms have different best/worst/average cases — need to specify which case to test
- Very slow algorithms (O(2ⁿ)) may timeout on large inputs — need adaptive size progression with early termination

---

## 3. New Grading Frontiers

### RFC 3.1: MutationTestingGrader — Grading Student Test Suites

**Feature Name:** Test-Driven Grading via Mutation Testing  
**Target Persona:** Professor (Software Engineering / TDD courses), Student (testing skills)

**The Concept:**  
Instead of grading the student's *implementation*, grade the quality of the student's *test suite*. The system injects known mutations (bugs) into a reference implementation and checks whether the student's tests catch them. A high mutation kill rate = a thorough test suite. This teaches students that writing tests is as important as writing code.

**Technical Implementation:**
- New template: `autograder/template_library/mutation_testing.py`
- New `TestFunction` subclasses:
  - `MutationKillRateTest` — Injects mutations, runs student tests, computes kill rate
  - `CoverageThresholdTest` — Runs student tests with coverage tooling, checks line/branch coverage
- Mutation operators (configurable per language):
  - Arithmetic: `+` → `-`, `*` → `/`
  - Conditional: `>` → `>=`, `==` → `!=`
  - Return value: `return x` → `return None`
- Workflow:
  1. Professor provides reference implementation + list of mutation operators
  2. System generates N mutants in sandbox
  3. Student test suite runs against each mutant
  4. Score = (killed mutants / total mutants) × 100
- Leverages existing `SandboxContainer.prepare_workdir()` to inject mutated files

**Challenges:**
- Equivalent mutants (mutations that don't change behavior) inflate denominator — need manual curation or heuristic filtering
- Compute-intensive: N mutants × M tests = N×M executions per submission
- Language-specific mutation operators require per-language AST manipulation (can leverage `StructuralAnalysisStep` roots)
- Students may write tests that pass for wrong reasons (testing implementation details vs. behavior)

---

### RFC 3.2: MaintainabilityScorer — Industry-Standard Code Quality Metrics

**Feature Name:** MaintainabilityScorer  
**Target Persona:** Professor (Software Engineering), Platform Admin (institutional quality standards)

**The Concept:**  
A grading dimension that scores code against industry maintainability metrics: cyclomatic complexity, cognitive complexity, coupling/cohesion, naming convention adherence, and documentation density. Produces a "Maintainability Index" (inspired by SonarQube/CodeClimate) that can be weighted alongside functional correctness in the criteria tree.

**Technical Implementation:**
- New `AiTestFunction` subclass: `autograder/template_library/static_analysis.py` → `MaintainabilityScoreTest`
- Hybrid approach:
  1. **Deterministic metrics** (computed from AST via `StructuralAnalysisResult`):
     - Cyclomatic complexity per function
     - Max nesting depth
     - Function/method length
     - Module coupling (import graph analysis)
  2. **AI-evaluated metrics** (via existing `AiBatchStep`):
     - Naming quality (semantic meaningfulness)
     - Documentation completeness and clarity
     - Design pattern recognition
- Composite score formula: `0.4 * deterministic_score + 0.6 * ai_score` (configurable weights)
- Integrates with existing `static_analysis.py` template — extends it with new test functions
- Results feed into the standard `TestResultNode` → `SubjectResultNode` hierarchy

**Challenges:**
- "Good naming" is subjective — AI evaluation may disagree with professor's standards; need calibration via few-shot examples
- Different languages have different idioms (Python's `snake_case` vs Java's `camelCase`) — language-aware rules needed
- Students may game metrics (splitting functions artificially to reduce complexity) — need holistic assessment
- Compute cost of AI evaluation for every submission adds latency and API spend

---

## 4. Deep AI Integration

### RFC 4.1: SocraticTutorAgent — Conversational Debugging Companion

**Feature Name:** SocraticTutorAgent  
**Target Persona:** Student (all levels), Professor (reduced office hours load)

**The Concept:**  
An agentic AI system that, upon grading completion, analyzes the student's failures and initiates a Socratic dialogue — asking guiding questions rather than giving answers. It uses the grading results, the student's code, and the criteria tree to identify *conceptual gaps* (not just syntax errors) and leads the student toward understanding through progressive hints. The agent has access to the sandbox and can run modified versions of the student's code to demonstrate concepts.

**Technical Implementation:**
- New service: `autograder/services/tutor/socratic_agent.py`
- Architecture: Multi-turn conversational agent with tool access
  - Tools available to agent: `run_code_in_sandbox`, `show_test_result`, `highlight_code_section`, `provide_hint`
  - Context: Full `PipelineExecution` result, criteria tree, student code, test reports
- Integration point: New API endpoint in `web/api/v1/tutor.py` — POST `/submissions/{id}/tutor/chat`
- Agent prompt engineering:
  - System prompt encodes Socratic method rules (never give direct answers, ask leading questions)
  - Includes the specific `TestResultNode` failures as context
  - Progressive hint levels: conceptual → structural → near-solution
- Conversation state stored in `web/database/models/tutor_session.py` (SQLAlchemy model)
- Rate limiting: Max 10 interactions per submission to prevent over-reliance

**Challenges:**
- Hallucination risk: AI may suggest incorrect fixes or misidentify the root cause — need guardrails (validate suggestions against sandbox execution)
- Latency: Multi-turn conversations need sub-2s response times for good UX — may need streaming responses
- Cost: Each student interaction = API call; at university scale (500 students × 10 interactions × 10 assignments) = 50K calls/semester
- Pedagogical validity: Need educator oversight to ensure the agent teaches correctly — configurable "teaching style" per professor
- Students may try to extract answers through prompt injection — need robust system prompt boundaries

---

### RFC 4.2: PredictiveStruggleDetector — Early Warning System

**Feature Name:** PredictiveStruggleDetector  
**Target Persona:** Professor (student success), Platform Admin (retention metrics)

**The Concept:**  
An ML-powered system that analyzes patterns across a student's submission history — declining scores, repeated failures on the same concept, increasing time between submissions, specific error patterns — to predict which students are at risk of falling behind *before* they fail. Generates proactive alerts to professors with specific intervention recommendations.

**Technical Implementation:**
- New service: `autograder/services/analytics/struggle_detector.py`
- Data pipeline:
  1. After each `PipelineExecution`, emit an event to an analytics queue (leverages existing `UpstashDriver` as message broker)
  2. Background worker aggregates per-student metrics:
     - Score trajectory (slope of recent N submissions)
     - Concept mastery map (which `CategoryNode`/`SubjectNode` consistently fail)
     - Submission frequency and timing patterns
     - Error type clustering (compile errors vs. logic errors vs. style issues)
  3. ML model (lightweight gradient boosting, trained on historical data) predicts "struggle probability"
- Alert system: Integrates with the webhook/event system from Feature Roadmap Item 4
- Dashboard data exposed via new endpoint: `web/api/v1/analytics.py` → GET `/assignments/{id}/at-risk-students`
- Database: New `web/database/models/student_analytics.py` table tracking longitudinal metrics

**Challenges:**
- Cold start: Needs historical data to train — initial deployments will have low accuracy until sufficient data accumulates
- Privacy: Tracking student behavior patterns raises FERPA/GDPR concerns — need anonymization and consent mechanisms
- False positives: Flagging students incorrectly can be stigmatizing — need high precision threshold before alerting
- Causality vs. correlation: A student submitting less frequently might be confident, not struggling — need multi-signal approach
- Model drift: Student populations change semester to semester — need periodic retraining

---

## 5. Ecosystem & Developer Experience (DX)

### RFC 5.1: LiveGradingLSP — Real-Time IDE Feedback

**Feature Name:** LiveGradingLSP (Language Server Protocol Integration)  
**Target Persona:** Student (immediate feedback loop), Professor (reduced grading anxiety)

**The Concept:**  
An LSP-compatible server that runs a lightweight subset of the grading pipeline in real-time as students type in their IDE (VS Code, IntelliJ, etc.). Students see inline diagnostics — not just syntax errors, but grading-relevant feedback like "this function doesn't handle the edge case required by Test 3" or "your HTML is missing the required `<nav>` element" — before they even submit.

**Technical Implementation:**
- New standalone service: `autograder/lsp/server.py` (using `pygls` library)
- Architecture:
  - LSP server connects to a running Autograder instance via internal API
  - On `textDocument/didChange`, debounce (500ms), then run lightweight checks:
    - Static analysis tests (from `static_analysis.py` template) — instant
    - Structural checks (from `StructuralAnalysisStep`) — instant
    - AI-based checks — batched, async, shown as "pending" diagnostics
  - Full sandbox-based tests NOT run in real-time (too slow) — only on explicit "pre-submit check" command
- Diagnostic mapping: Each `TestFunction` that supports LSP mode implements `to_diagnostic()` returning LSP `Diagnostic` objects with line/column ranges
- VS Code extension: `autograder-vscode/` package that installs the LSP client and provides:
  - Inline grading hints as warnings/info diagnostics
  - "Grading Progress" sidebar showing criteria tree with live check/cross marks
  - "Pre-Submit Check" command that runs full pipeline
- Configuration: Student installs extension, enters assignment URL → extension fetches criteria tree and connects to LSP

**Challenges:**
- Latency budget: Must respond within 200ms for typing feedback — limits to pre-computed/cached checks only
- Partial code: Students' in-progress code may not parse — need graceful degradation (show what's checkable)
- Resource consumption: Running per-keystroke analysis for 200 concurrent students requires efficient server architecture (async, connection pooling)
- Security: LSP server must not expose grading criteria details that professors want hidden — need "hint mode" vs "full mode"
- IDE fragmentation: Supporting VS Code, IntelliJ, Vim/Neovim requires LSP compliance but each has UX quirks

---

### RFC 5.2: LMSGradebookSync — Webhook-Driven LMS Integration

**Feature Name:** LMSGradebookSync  
**Target Persona:** Professor (zero manual grade entry), Platform Admin (institutional compliance)

**The Concept:**  
A bidirectional sync layer that automatically pushes grading results to institutional LMS platforms (Canvas, Moodle, Blackboard) via their APIs, and pulls assignment metadata (deadlines, student rosters, rubric mappings) from the LMS into the Autograder. Professors configure once; grades flow automatically.

**Technical Implementation:**
- New module: `web/integrations/lms/` with adapter pattern:
  - `lms_adapter.py` — abstract interface (`push_grade`, `pull_roster`, `pull_assignment`)
  - `canvas_adapter.py` — Canvas REST API implementation (OAuth2 + LTI 1.3)
  - `moodle_adapter.py` — Moodle Web Services API implementation
- Event-driven architecture:
  - Leverages the webhook system (Feature Roadmap Item 4)
  - On `grading_complete` event → `LMSSyncWorker` picks up the event → maps internal score to LMS gradebook entry → pushes via adapter
- Configuration stored in `web/database/models/lms_config.py`:
  - LMS type, API credentials (encrypted), course mapping, assignment mapping, grade scale conversion
- Roster sync: Periodic pull (configurable interval) maps LMS student IDs to Autograder `user_id`
- Grade mapping: Configurable conversion (percentage → letter grade, percentage → points, custom scales)
- Retry logic: Failed pushes queued with exponential backoff (3 retries, then alert professor)

**Challenges:**
- LMS API instability: Canvas/Moodle APIs change without notice — need version-pinned adapters with integration tests
- Authentication complexity: LTI 1.3 / OAuth2 flows are notoriously difficult to implement correctly — consider using established libraries
- Grade conflicts: If a professor manually overrides a grade in the LMS, the next sync shouldn't overwrite it — need conflict resolution strategy (LMS-wins vs. Autograder-wins vs. alert)
- Scale: Batch grade pushes for 500-student courses must respect API rate limits (Canvas: 700 req/min)
- Data mapping: Different LMS platforms model assignments/rubrics differently — the adapter layer must normalize these

---

## Architecture Evolution Notes

For the features above to scale to university-level loads, the following architectural patterns should be considered:

| Pattern | Application |
|---------|-------------|
| **Event-Driven (CQRS)** | Decouple grading execution from result consumption. `PipelineExecution` emits domain events; analytics, LMS sync, and plagiarism corpus all consume independently. |
| **MicroVM Snapshotting** | Replace Docker containers with Firecracker microVMs for the sandbox layer. Pre-snapshot a warm VM per language; clone-on-demand gives <125ms cold starts vs. Docker's 2-3s. Critical for `ComplexityProfilingStep` (many executions) and `MutationTestingGrader` (N×M runs). |
| **Agentic Orchestration** | The `SocraticTutorAgent` and `PredictiveStruggleDetector` operate as autonomous agents with tool access, not simple request-response services. Use a lightweight agent framework (LangGraph or custom) with the pipeline's `PipelineExecution` as shared memory. |
| **DDD Bounded Contexts** | As the system grows, separate: Grading Core (pipeline), Analytics (struggle detection), Integrations (LMS/webhooks), and Tutoring (Socratic agent) into distinct bounded contexts with explicit contracts. |

---

## Priority Matrix

| Feature | Impact | Effort | Recommended Phase |
|---------|--------|--------|-------------------|
| SQLValidationTemplate | High | Medium | Phase 1 (Q3 2026) |
| LMSGradebookSync | High | Medium | Phase 1 (Q3 2026) |
| PlagiarismDetectionStep | High | High | Phase 2 (Q4 2026) |
| MaintainabilityScorer | Medium | Low | Phase 2 (Q4 2026) |
| ComplexityProfilingStep | Medium | Medium | Phase 2 (Q4 2026) |
| DataScienceTemplate | High | High | Phase 3 (Q1 2027) |
| MutationTestingGrader | High | High | Phase 3 (Q1 2027) |
| PredictiveStruggleDetector | High | Very High | Phase 3 (Q1 2027) |
| SocraticTutorAgent | Very High | Very High | Phase 4 (Q2 2027) |
| LiveGradingLSP | Very High | Very High | Phase 4 (Q2 2027) |

---

## Conclusion

The Autograder's clean abstractions (`Step`, `TestFunction`, `AiTestFunction`, `Template`) make it remarkably extensible. Every feature above plugs into existing extension points without requiring core rewrites — a testament to the current architecture's foresight. The path forward is clear: expand the template library for new domains, enrich the pipeline with intelligence steps, deepen AI integration from reactive to agentic, and connect the engine to the broader educational ecosystem.
