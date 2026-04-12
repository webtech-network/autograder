# Feedback Generation

## What it is

Feedback generation transforms grading data into student-facing guidance.

In this architecture, feedback is generated from:

- `ResultTree` (full scoring structure)
- `Focus` (tests ranked by score impact)
- `FeedbackPreferences` (report configuration)

## Why it matters

A grading system is educational only when results are understandable and actionable. Feedback is the layer that turns "a score" into "a next learning step."

## Pipeline position

```text
... -> GRADE -> FOCUS -> FEEDBACK -> ...
```

Feedback runs only when `include_feedback=True`.

## How it works

1. `FeedbackStep` reads focus and result tree from `PipelineExecution`.
2. `ReporterService` selects reporter mode:
   - `default` -> `DefaultReporter`
   - `ai` -> `AiReporter` (not implemented yet)
3. Preferences are parsed from `feedback_config`.
4. Reporter returns Markdown content.

## Educational quality patterns

High-quality reports should:

- prioritize high-impact failures first
- keep feedback objective and rubric-aligned
- include targeted learning resources where possible
- separate required improvements from bonus opportunities

## Linking resources to criteria

`online_content` resources can be linked to specific test names. This lets the report include remediation links only when relevant tests fail.

## Common mistakes

- Long generic feedback that ignores focus ordering
- Hiding score breakdown while expecting students to self-diagnose
- Enabling AI mode in production before AI reporter implementation is complete

## Continue reading

- [Pipeline Step: Feedback](../pipeline/07-feedback.md)
- [Focus Feature](../features/focus_feature.md)
- [Educational Criteria Design](../guides/criteria-tree-educational-standards.md)
