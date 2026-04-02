# Pipeline Documentation

## Overview

The autograder is built around a **pipeline architecture** — a sequential chain of steps that transforms a raw student submission into a graded result with scores, feedback, and optional exports. The pipeline is the central orchestration mechanism of the entire system.

The pipeline is:
- **Stateless and reusable**: A single pipeline instance can grade any number of submissions sequentially.
- **Configuration-driven**: Steps are added based on the grading configuration, so different assignments can have different pipeline shapes.
- **Fail-fast**: If any step fails, the pipeline stops immediately and reports the failure point.

```
Submission ──▶ [LOAD_TEMPLATE] ──▶ [BUILD_TREE] ──▶ [SANDBOX] ──▶ [PRE_FLIGHT] ──▶ [AI_BATCH] ──▶ [GRADE] ──▶ [FOCUS] ──▶ [FEEDBACK] ──▶ [EXPORT]
                                                                                                                             │
                                                                                                                     PipelineExecution
                                                                                                                     (with GradingResult)
```

---

## Core Architecture

### AutograderPipeline

The `AutograderPipeline` class (`autograder/autograder.py`) is the orchestrator. It holds an ordered dictionary of steps and executes them sequentially, passing a shared `PipelineExecution` object through each one.

```python
pipeline = AutograderPipeline()
pipeline.add_step(StepName.LOAD_TEMPLATE, TemplateLoaderStep("input_output"))
pipeline.add_step(StepName.BUILD_TREE, BuildTreeStep(criteria_json))
pipeline.add_step(StepName.GRADE, GradeStep())
# ...

result = pipeline.run(submission)
```

Key behaviors:
- Steps are executed in insertion order.
- After each step, the pipeline checks the latest `StepResult`. If it failed, the pipeline sets its status to `FAILED` and breaks.
- Unhandled exceptions set the status to `INTERRUPTED`.
- After all steps (or early exit), `finish_execution()` is called to assemble the final `GradingResult`.
- Sandbox cleanup always runs at the end, regardless of success or failure.

### PipelineExecution

`PipelineExecution` (`autograder/models/pipeline_execution.py`) is the shared state object that flows through every step. It acts as both the execution context and the audit trail.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `submission` | `Submission` | The original student submission (files, language, metadata) |
| `step_results` | `List[StepResult]` | Ordered list of results from each executed step |
| `assignment_id` | `int` | Identifier for the assignment being graded |
| `status` | `PipelineStatus` | Current execution status |
| `result` | `GradingResult \| None` | Final grading result, populated after `finish_execution()` |
| `start_time` | `float` | Timestamp when execution started |

**Status lifecycle:**

```
EMPTY ──▶ RUNNING ──▶ SUCCESS
                  ──▶ FAILED       (a step returned StepStatus.FAIL)
                  ──▶ INTERRUPTED  (unhandled exception)
```

**Key methods:**

- `add_step_result(step_result)` — Appends a step result and returns `self` for chaining.
- `get_step_result(step_name)` — Retrieves the result of a specific step by name. Raises `ValueError` if the step was never executed.
- `has_step_result(step_name)` — Checks if a step was executed.
- `get_previous_step()` — Returns the most recently added step result.
- `finish_execution()` — Assembles the `GradingResult` from the GRADE, FOCUS, and FEEDBACK step results if the pipeline succeeded.
- `PipelineExecutionSerializer.serialize(execution)` — Generates a structured dictionary for API responses with step details, timing, and error information.

### StepResult

Each step produces a `StepResult` (`autograder/models/dataclass/step_result.py`) — a generic container for step output.

```python
@dataclass
class StepResult(Generic[T]):
    step: StepName          # Which step produced this
    data: T                 # Step-specific output (template, tree, sandbox, scores, etc.)
    status: StepStatus      # SUCCESS or FAIL
    error: Optional[str]    # Error message if failed
    original_input: Any     # Optional reference to input data
```

The `data` field is polymorphic — each step stores a different type:

| Step | `data` type |
|------|-------------|
| BOOTSTRAP | `Submission` |
| LOAD_TEMPLATE | `Template` |
| BUILD_TREE | `CriteriaTree` |
| PRE_FLIGHT | `None` |
| SANDBOX | `SandboxContainer | None` |
| GRADE | `GradeStepResult` |
| FOCUS | `Focus` |
| FEEDBACK | `str` (Markdown feedback) |
| EXPORTER | `None` |

### Step Interface

All steps implement the `Step` abstract class:

```python
class Step(ABC):
    @abstractmethod
    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Execute the step on the pipeline execution context."""
```

Every step receives the full `PipelineExecution`, reads what it needs from previous step results, performs its work, appends its own `StepResult`, and returns the updated `PipelineExecution`.

---

## Step Dependencies

Steps read data from previous steps via `pipeline_exec.get_step_result(StepName.X)`. This creates implicit dependencies:

| Step | Requires |
|------|----------|
| **Load Template** | — (no dependencies) |
| **Build Tree** | Load Template (needs the `Template` to match test functions) |
| **Sandbox** | Load Template (checks if template requires sandbox) |
| **Pre-Flight** | Load Template, Sandbox (requires sandbox to run setup commands) |
| **Grade** | Load Template, Build Tree, Sandbox (optional — only if template requires sandbox) |
| **Focus** | Grade (needs the `ResultTree` from grading) |
| **Feedback** | Grade, Focus (needs the `ResultTree` and `Focus` objects) |
| **Export** | Grade (needs the final score) |

The pipeline enforces ordering through insertion order, not through explicit dependency declarations. Steps are always added in the correct sequence by `build_pipeline()`.

---

## Pipeline Assembly

The `build_pipeline()` function (`autograder/autograder.py`) leverages the `StepRegistry` factory to construct pipelines declaratively from configuration parameters:

```python
pipeline = build_pipeline(
    template_name="input_output",
    include_feedback=True,
    grading_criteria=criteria_config,
    feedback_config=feedback_settings,
    setup_config={"python": {"required_files": ["main.py"]}},
    feedback_mode="ai",
    export_results=False,
)
```

**Assembly rules:**

The `StepRegistry` applies the specific conditionality parameters natively for step constructions:
1. **Load Template**, **Build Tree**, **Sandbox**, and **Pre-Flight** are unconditionally instantiated. 
3. **Grade** and **Focus** always evaluate into their respective steps.
4. **Feedback** strictly resolves if `include_feedback=True`, consuming the `ReporterService` using the designated `feedback_mode`.
5. **Export** compiles optionally through `export_results=True`.

These instantiated elements are natively pushed into the `AutograderPipeline` linearly along their static `execution_order` mapping:

```
LOAD_TEMPLATE → BUILD_TREE → SANDBOX → PRE_FLIGHT → GRADE → FOCUS → FEEDBACK → EXPORT
```

---

## Available Steps

| Step | File | Description | Required Steps |
|------|------|-------------|----------------|
| [Load Template](01-load-template.md) | `load_template_step.py` | Loads the grading template (built-in or custom) containing test functions | None |
| [Build Tree](02-build-tree.md) | `build_tree_step.py` | Constructs the `CriteriaTree` from JSON config, matching test functions from the template | Load Template |
| [Sandbox](03-sandbox.md) | `sandbox_step.py` | Creates the sandbox environment and prepares the workspace | Load Template |
| [Pre-Flight](04-pre-flight.md) | `pre_flight_step.py` | Validates required files and executes setup commands (compilation, etc.) | Sandbox |
| [Grade](05-grade.md) | `grade_step.py` | Executes all tests against the submission and produces the scored `ResultTree` | Load Template, Build Tree, Sandbox* |
| [Focus](06-focus.md) | `focus_step.py` | Ranks all tests by their impact on the final score | Grade |
| [Feedback](07-feedback.md) | `feedback_step.py` | Generates student-facing feedback reports (default or AI-powered) | Focus |
| [Export](08-export.md) | `export_step.py` | Sends the final score to an external system (e.g., Upstash/Redis) | Grade |

\* Sandbox is only required if the template requires sandbox execution.

---

## Error Handling and Sandbox Cleanup

When a step fails:
1. The step returns a `StepResult` with `status=StepStatus.FAIL` and an `error` message.
2. The pipeline detects the failure via `get_previous_step()` and calls `set_failure()`.
3. No further steps are executed.
4. `finish_execution()` is called — since the status is `FAILED`, `result` remains `None`.
5. Sandbox cleanup always runs: if a Sandbox step created a sandbox, it is released back to the pool regardless of pipeline outcome.

For unhandled exceptions, the status is set to `INTERRUPTED` and the same cleanup logic applies.

The `PipelineExecutionSerializer` provides structured error reporting in API responses. See [Pipeline Execution Tracking](../architecture/core_structures.md#pipeline-execution-summary) for details on how this surfaces in the API.

---

## Related Documentation

- [Core Data Structures](../architecture/core_structures.md) — CriteriaTree, ResultTree, Submission, GradingResult
- [Pipeline Execution Tracking](../architecture/pipeline_execution_tracking.md) — API response format for pipeline execution details
- [Setup Config Feature](../features/setup_config_feature.md) — Language-specific preflight configuration
- [Focus Feature](../features/focus_feature.md) — Deep dive on the focus ranking algorithm
- [Grading Engine](../features/grading_engine.md) — Deep dive on the tree-based grading engine
- [Configuration Examples](../guides/criteria_configuration_examples.md) — Real-world grading configurations
