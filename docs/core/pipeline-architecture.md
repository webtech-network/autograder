# Pipeline Architecture

## What it is

The Autograder pipeline is the execution backbone that turns one submission into a complete grading result.

Every run follows a fixed order built by `build_pipeline()`:

```text
LOAD_TEMPLATE -> BUILD_TREE -> SANDBOX -> PRE_FLIGHT -> AI_BATCH -> GRADE -> FOCUS -> FEEDBACK? -> EXPORT?
```

`FEEDBACK` and `EXPORT` are optional, based on configuration.

## Why it matters

- It keeps grading deterministic and debuggable.
- It separates concerns: each step has one responsibility.
- It makes extension safer: new behaviors can be added as steps, not scattered conditionals.

## How it works

1. `AutograderPipeline.run(submission)` creates a `PipelineExecution`.
2. Each step receives the same `PipelineExecution` and appends one `StepResult`.
3. If a step fails, execution stops early.
4. `finish_execution()` assembles `GradingResult` from grade/focus/feedback artifacts.
5. Sandbox cleanup runs at the end and destroys any sandbox used by the submission.

## Core data contract

`PipelineExecution` is the shared contract between steps:

- Submission data (`submission`)
- Ordered step outputs (`step_results`)
- Runtime status (`status`)
- Final result (`result`)

Typed accessors such as `get_loaded_template()`, `get_built_criteria_tree()`, `get_result_tree()`, and `get_focus()` prevent ad-hoc data access in step implementations.

## Example mental model

Think of the pipeline as a production line:

- **Load Template** chooses the toolset
- **Build Tree** builds the rubric structure
- **Sandbox + Pre-Flight** prepares a safe execution environment
- **Grade** produces raw scoring results
- **Focus + Feedback** convert scoring into learning guidance

## Common mistakes

- Treating steps as independent services without respecting step order dependencies
- Generating feedback without focus data
- Documenting only successful flow and skipping fail-fast behavior

## Continue reading

- [Pipeline Deep Dive](../pipeline/README.md)
- [Pipeline Execution Tracking](../architecture/pipeline_execution_tracking.md)
- [Feedback Generation](feedback-generation.md)
