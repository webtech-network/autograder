# Read a result

Every grading ends in one *outcome*, the same JSON document whichever host
graded it: the HTTP API returns it in a submission's details, the GitHub
Action saves it as `.autograder/outcome.json`. This page reads the outcome of
the tutorial's [bad Python submission](tutorial.md#1-a-python-program-that-reads-input).
The complete format is the [outcome contract](../contracts/OUTCOMES.md).

## Completed or failed

`status` says whether the submission was graded:

* `completed`: `score` is the final score, from 0 to 100, and `tree` holds
  every criterion's result. A score of 0 is a real grade: the student's
  program ran and failed every check.
* `failed`: the submission could not be graded. `score` and `tree` are
  `null`, never 0, and `error` says why.

## The score tree

`tree` repeats your rubric with a score on every node. Each criterion carries
its `id`, its evaluator, its effective `weight` within its group, its `score`
and its `report`, the explanation the student sees. A category's `weight` is
the points it moves: 100 for `base`, `max_points` for `bonus` and `penalty`:

<!-- outcome: examples/tutorial/python-io/bad -->
```json
{
  "status": "completed",
  "score": 60.0,
  "tree": {
    "score": 60.0,
    "base": {
      "score": 80.0,
      "weight": 100.0,
      "subjects": [
        {
          "name": "Adds two numbers",
          "score": 100.0,
          "weight": 80.0,
          "tests": [
            {"id": "sum-positive", "evaluator": "expect_output", "score": 100.0, "weight": 50.0},
            {"id": "sum-negative", "evaluator": "expect_output", "score": 100.0, "weight": 50.0}
          ]
        },
        {
          "name": "Handles bad input",
          "score": 0.0,
          "weight": 20.0,
          "tests": [{"id": "text-input", "evaluator": "dont_fail", "score": 0.0, "weight": 100.0}]
        }
      ]
    },
    "bonus": null,
    "penalty": {
      "score": 0.0,
      "weight": 20.0,
      "tests": [{"id": "no-eval", "evaluator": "forbidden_keyword", "score": 0.0, "weight": 100.0}]
    }
  },
  "feedback": {"status": "completed"},
  "error": null
}
```

The penalty category scores 0 because its only criterion did: the student
called `eval`. [Scores](scoring.md) turns these numbers into the final 60.

## The report

`feedback.content` is the report the student reads, in Markdown:

<!-- report: examples/tutorial/python-io/bad -->
```markdown
# Evaluation Report

**Final score: 60.00 / 100**

---

## Summary

| Category | Passed | Points |
| --- | --- | --- |
| Requirements | 2 / 3 | −20.00 points |
| Penalties | 0 / 1 | −20.00 of 20.00 points |

100 − 20.00 − 20.00 = **60.00 / 100**

---

## Requirements · 80.00 / 100 · −20.00 points

### Handles bad input · 0.00 / 100 · −20.00 points

- ❌ **Does not crash on text input** · 0.00 / 100 · −20.00 points

  FAILURE: Your program crashed during execution.
  Error:
  Traceback (most recent call last):
    File "/app/main.py", line 2, in <module>
      b = input()
  EOFError: EOF when reading a line

### Adds two numbers · 100.00 / 100

✅ All tests passed (2).

---

## Penalties · −20.00 of 20.00 points

- ❌ **Does not call eval** · 0.00 / 100 · −20.00 points

  FAILURE: Forbidden language constructs detected:
    - Forbidden construct 'eval($$$)' found in 'main.py'
```

`feedback.status` is `disabled` when the definition does not enable feedback,
and `failed` (with an `error`) when the report could not be written; the
grade is the same either way.

## When a submission is not graded

A failed outcome's `error` has a `code`, a `category`, a `message` and
`retryable`. Errors of category `submission` are about the student's work,
and their `message` explains what to fix in the submission's language:

| `code` | What happened |
| --- | --- |
| `REQUIRED_FILE_MISSING` | A required file, or a file a criterion needs, is missing. |
| `PREPARATION_FAILED` | A setup command failed, typically a compilation error; `error.output` holds an excerpt of its output unless the step is `private_output`. |
| `LANGUAGE_REQUIRED`, `LANGUAGE_NOT_ALLOWED` | The submission named no language, or one the definition does not allow. |
| `AMBIGUOUS_FILE_TARGET` | A check of one file found several; name one in the criterion's `file`. |

Other categories are not the student's fault: `capability` (the host lacks
something the definition needs, such as a language runtime or a sandbox in
time), `provider` (an AI provider failed) and `internal`. When `retryable` is
`true`, grading the same submission again may succeed. Every code is listed in
the [outcome contract](../contracts/OUTCOMES.md).
