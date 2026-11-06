# Requested feedback

Feedback is an optional derivation of a completed grade. Only when the
definition's `feedback.enabled` is true does the coordinator call
`render_feedback(tree, preferences, locale)` (`autograder/services/feedback.py`)
with the completed `ResultOutcomeTree`, the definition's canonical
`FeedbackPreferences` and the submission locale. It ranks criteria with
[focus](06-focus.md) and renders the one implemented mode, `default`, as Markdown
(`render_default_report`). There is no reporter factory or AI reporter.

| Definition | Feedback work | Outcome `feedback` |
|---|---|---|
| `enabled: false` | none (focus and reporting are never called) | `disabled`, no content, no error |
| `enabled: true`, report rendered | focus + default report | `completed` with Markdown content |
| `enabled: true`, any exception or empty content | logged with the execution ID | `failed` with `FEEDBACK_ERROR` and a fixed safe message; the grade is unchanged |

Rendering only reads its inputs: titles and category headings fall back to
localized defaults at render time, so preferences and results are never
modified and rendering twice gives the same text. The report keeps the
localized headings, optional summary and final score, hides passed criteria
unless `show_passed_tests`, orders failed criteria by points lost, and shows a
learning resource when it links no criteria or when one of its linked criterion
IDs failed.
Every preference, with its type and default, is listed in the generated
[definition reference](../reference/definition.md#feedbackpreferences).

Publication happens after cleanup and finalization in the
[hosting adapter](08-export.md), outside grading.
