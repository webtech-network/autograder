# Step 6: Feedback

## Purpose

The Feedback step generates a student-facing report from the grading results. It transforms raw scores and test data into readable, actionable feedback that helps students understand their grade and what to improve.

## How It Works

1. **Retrieve focus data** — The step reads the `Focus` object from the previous step, which contains all tests ranked by their impact on the final score.
2. **Delegate to reporter** — The `ReporterService` is initialized with a feedback mode and delegates report generation to the appropriate reporter implementation.
3. **Store feedback** — The generated feedback (typically a markdown-formatted string) is stored in the step result.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Focus** | The `Focus` object with tests ranked by impact |

## Input

| Source | Data |
|--------|------|
| Constructor | `reporter_service: ReporterService` — configured with the feedback mode |
| Constructor | `feedback_config: dict` — additional feedback preferences |
| Pipeline | `StepName.FOCUS` → `Focus` |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | Feedback content (string) | The generated student-facing report |
| `status` | `StepStatus.SUCCESS` | On successful generation |

## Feedback Modes

The `ReporterService` supports two modes, selected at pipeline assembly time:

| Mode | Reporter | Description |
|------|----------|-------------|
| `"default"` | `DefaultReporter` | Structured report with test results and scores |
| `"ai"` | `AiReporter` | AI-generated conversational feedback (placeholder — not yet fully implemented) |

The mode is passed to `build_pipeline()` via the `feedback_mode` parameter and forwarded to the `ReporterService` constructor.

## Feedback Configuration

The `feedback_config` dictionary allows customization of the generated feedback. It is passed through to the reporter's `generate_feedback()` method alongside the focus data. Configuration options are defined by the `FeedbackPreferences` dataclass, which supports:

- `GeneralPreferences` — General feedback settings
- `DefaultReporterPreferences` — Settings specific to the default reporter
- `AiReporterPreferences` — Settings specific to the AI reporter
- `LearningResource` — Optional learning resources to include in feedback

## Conditional Inclusion

This step is only added to the pipeline when `include_feedback=True` is passed to `build_pipeline()`. When omitted, the pipeline skips feedback generation entirely — the `GradingResult` will have `feedback=None`.

## Failure Scenarios

- Focus step result missing → exception caught, `StepStatus.FAIL`.
- Reporter raises an exception during generation → `StepStatus.FAIL` with error message.

## Source

`autograder/steps/feedback_step.py` → `FeedbackStep`

`autograder/services/report/reporter_service.py` → `ReporterService`

`autograder/services/report/default_reporter.py` → `DefaultReporter`

`autograder/services/report/ai_reporter.py` → `AiReporter`
