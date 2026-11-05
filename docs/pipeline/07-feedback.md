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
modified and rendering twice gives the same text.

The report explains the grade with the authored rubric:

1. The title and the final score.
2. A summary table (`add_report_summary`): per category, tests passed and the
   points it moved the score, then the equation
   `100 − base − penalty + bonus = final`, noting when the 0–100 limit applied.
3. One section per category (base, then penalty, then bonus) following the
   authored tree: each subject is a nested heading with its score and points,
   and each test shows its status (✅ full, ⚠️ partial, ❌ zero), file target,
   score, the points it lost (base, penalty) or earned (bonus) and its
   evaluator's report. A holder's own tests come before its subjects; siblings
   are ordered by points missed.
4. Learning resources: a resource shows when it links no criteria or when one
   of its linked criterion IDs failed.

The numbers come from the shared scoring values (`criterion_points` and
focus), never recomputed. Parameters are never rendered: a value such as an
expected output appears only if the evaluator's report includes it. Headings
hold the neutral category name (or `category_headers`) and numbers, so they
cannot contradict the status. `show_score: false` hides every number;
passing tests are listed only with `show_passed_tests`, otherwise a fully
passing holder says so in one line.

Publication happens after cleanup and finalization in the
[hosting adapter](08-export.md), outside grading.
