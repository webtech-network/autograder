# Step 6: Feedback

## Purpose

The Feedback step generates a student-facing report from the grading results. It transforms raw scores and test data into readable, actionable feedback that helps students understand their grade and identify the most impactful areas for improvement.

## How It Works

1. **Retrieve focus data** — The step reads the `Focus` object from the previous step, which contains tests ranked by their impact on the final score.
2. **Delegate to reporter** — The `ReporterService` is initialized with a `feedback_mode` and delegates report generation to the appropriate reporter implementation.
3. **Parse configuration** — The `FeedbackPreferences` are constructed from the provided `feedback_config` dictionary, ensuring type safety and default values.
4. **Generate report** — The active reporter (`DefaultReporter` or `AiReporter`) generates the feedback content (typically Markdown) using the focus data, the full results tree, and the parsed preferences.
5. **Store result** — The generated report is wrapped in a `StepResult` and added to the pipeline execution.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Grade** | The `ResultTree` containing the full score hierarchy |
| **Focus** | The `Focus` object with tests ranked by impact |

## Input

| Source | Data |
|--------|------|
| Constructor | `reporter_service: ReporterService` — configured with the feedback mode |
| Constructor | `feedback_config: dict` — additional feedback preferences |
| Pipeline | `StepName.GRADE` → `GradeStepResult.result_tree` |
| Pipeline | `StepName.FOCUS` → `Focus` |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `str` | The generated student-facing report (Markdown) |
| `status` | `StepStatus.SUCCESS` | On successful generation |

## Feedback Modes

The mode is selected at pipeline assembly time via `build_pipeline(..., feedback_mode="...")`:

| Mode | Reporter | Description |
|------|----------|-------------|
| `"default"` | `DefaultReporter` | Structured Markdown report with icons, summaries, and categorized results |
| `"ai"` | `AiReporter` | AI-generated conversational feedback (currently a placeholder) |

## Feedback Configuration

The `feedback_config` allows deep customization of the report. It is mapped to the `FeedbackPreferences` dataclass hierarchy:

### General Preferences (`general`)

| Field | Default | Description |
|-------|---------|-------------|
| `report_title` | `"Relatório de Avaliação"` | Main title of the feedback document |
| `show_score` | `True` | Whether to include the final score block |
| `show_passed_tests` | `False` | If True, includes successful tests in the report |
| `add_report_summary` | `True` | Includes a summary section with total/passed/failed counts |
| `online_content` | `[]` | List of `LearningResource` objects |

### Learning Resources

Resources can be linked to specific tests to provide targeted help:

```python
{
    "url": "https://docs.python.org/3/library/functions.html#print",
    "description": "Output formatting guide",
    "linked_tests": ["test_print_output", "test_format_string"]
}
```

### Default Reporter Preferences (`default`)

| Field | Description |
|-------|-------------|
| `category_headers` | Dict mapping category names (`base`, `bonus`, `penalty`) to custom display headers |

*Example:* `{"base": "🚀 Core Requirements", "penalty": "⚠️ Critical Fixes"}`

### AI Reporter Preferences (`ai`)

*Note: These are planned configuration options for the upcoming AI implementation.*

| Field | Description |
|-------|-------------|
| `provide_solutions` | Strategy for solutions (e.g., `"hint"`, `"none"`, `"full"`) |
| `feedback_tone` | The "voice" of the AI (e.g., `"encouraging but direct"`) |
| `feedback_persona` | The AI character (e.g., `"Code Buddy"`) |
| `assignment_context` | Additional background for the LLM prompt |

## Conditional Inclusion

This step is only added to the pipeline when `include_feedback=True` is passed to `build_pipeline()`. When omitted, the pipeline skips feedback generation — the `GradingResult` will move directly to the Export step.

## Failure Scenarios

- Missing dependency results (Focus or Grade) → `StepStatus.FAIL`.
- Malformed configuration (e.g., incorrect types in the config dict) → `StepStatus.FAIL`.
- Runtime error during reporter generation → `StepStatus.FAIL` with error details.

## Source

`autograder/steps/feedback_step.py` → `FeedbackStep`

`autograder/services/report/` → `ReporterService`, `DefaultReporter`, `AiReporter`

`autograder/models/dataclass/feedback_preferences.py` → `FeedbackPreferences`
