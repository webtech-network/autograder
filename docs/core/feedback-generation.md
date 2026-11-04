# Feedback Generation

## What it is

Feedback generation transforms grading data into student-facing guidance.

In this architecture, feedback is generated from:

- the completed canonical `ResultOutcomeTree` (full scoring structure)
- `Focus` (criteria ranked by score impact, derived from that tree)
- the definition's validated `feedback.preferences` (report configuration)

## Why it matters

A grading system is educational only when results are understandable and actionable. Feedback is the layer that turns "a score" into "a next learning step."

## Pipeline position

```text
... -> GRADE -> FOCUS -> FEEDBACK -> ...
```

Feedback and focus run only when the definition has `feedback.enabled=true`.

## How it works

1. The coordinator calls `render_feedback(tree, preferences, locale)` only when
   feedback is enabled; otherwise feedback stays `disabled` and nothing runs.
2. `find_focus(tree)` ranks criteria by points lost.
3. `render_default_report` renders the one implemented `default` mode as Markdown,
   reading (never modifying) the canonical preferences.
4. Exceptions or empty content mark feedback `failed` (`FEEDBACK_ERROR`) and
   preserve the grade.

## Educational quality patterns

High-quality reports should:

- prioritize high-impact failures first
- keep feedback objective and rubric-aligned
- include targeted learning resources where possible
- separate required improvements from bonus opportunities

## Linking resources to criteria

`online_content` resources can be linked to stable criterion IDs. This lets the report include remediation links only when relevant tests fail.

## Common mistakes

- Long generic feedback that ignores focus ordering
- Hiding score breakdown while expecting students to self-diagnose

## Continue reading

- [Requested feedback](../pipeline/07-feedback.md)
- [Focus Feature](../features/focus_feature.md)
- [Educational Criteria Design](../guides/criteria-tree-educational-standards.md)
