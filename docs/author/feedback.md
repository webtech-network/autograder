# Student feedback

With `"feedback": {"enabled": true}` every graded submission also gets a
Markdown report written for the student. Without it, grading produces the score
and the result tree only, and does no report work. The report never changes
the score, and if it cannot be written the grade still stands (feedback status
`failed`, code `FEEDBACK_ERROR`).

## What the report shows

The report follows your rubric, so the names you give subjects and criteria
are what the student reads:

1. A title and the final score.
2. A summary: for each category, how many criteria passed and how many points
   it moved the score, and the sum that gives the final score.
3. One section per category, `base` (headed "Requirements"), then `penalty`,
   then `bonus`. Each subject is a heading with its score and the points it
   lost or earned; each criterion shows ✅ (full), ⚠️ (partial) or ❌ (zero),
   its score, the points it cost or earned, and its evaluator's explanation,
   such as the error a program printed. Within a group, what cost the most
   points comes first. A group where everything passed collapses to one line.
4. Learning resources you linked to the criteria the student missed.

The report shows what the evaluator explains, never the criterion's
parameters: an expected output appears only when the evaluator's own message
includes it. [Read a result](results.md) shows a complete report.

## Preferences

<!-- fragment: examples/tutorial/python-io/definition.json -->
```json
{
  "feedback": {
    "enabled": true,
    "preferences": {
      "general": {
        "report_title": "Sum of two numbers: your result",
        "show_passed_tests": true,
        "online_content": [
          {
            "url": "https://docs.python.org/3/tutorial/errors.html#handling-exceptions",
            "description": "Handling exceptions in Python",
            "linked_tests": ["text-input"]
          }
        ]
      },
      "default": {"category_headers": {"penalty": "Rules"}}
    }
  }
}
```

| Preference | Effect |
| --- | --- |
| `report_title` | Replaces the default title. |
| `show_score` | `false` hides every number, leaving the statuses and explanations. |
| `show_passed_tests` | Lists passing criteria one by one instead of one line per passing group. |
| `add_report_summary` | `false` leaves out the summary table. |
| `online_content` | Learning resources. One appears when any criterion in its `linked_tests` (criterion `id`s) did not score 100, or always when `linked_tests` is empty. |
| `category_headers` | Your own headings for `base`, `bonus` and `penalty`. |

Types and defaults of each preference are in the
[definition reference](../reference/definition.md#generalpreferences).

## Language of the report

The report, the evaluators' explanations and the messages for submissions that
cannot be graded are written in the submission's locale: `en` (default) or
`pt-br`. Hosts take it per submission: the HTTP API's `locale` field, the
GitHub Action's `locale` input. Anything else is rejected rather than replaced
by English. Your own texts (criterion and subject names, titles, resource
descriptions) are shown as you wrote them.
