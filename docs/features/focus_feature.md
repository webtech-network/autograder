# Focus

## Overview

Focus orders assessed criteria by how many points each one cost on the final
score. It is an in-process value used to prioritize requested feedback; it is
not part of the terminal outcome, the HTTP API or the database.

```python
from autograder.services.focus_service import find_focus

focus = find_focus(outcome.tree)          # completed ResultOutcomeTree
focus.base[0].test_result.id              # the criterion that cost the most points
focus.base[0].diff_score                  # points lost on the 0-100 scale
```

`Focus` has `base`, `penalty` and `bonus` tuples (`None` for absent categories)
of `FocusedTest(test_result, diff_score)`. `test_result` is the tree's own
`TestOutcome`; both values are frozen.

## Impact

```
diff_score = (100 - score) * share
share      = category weight / 100 * product of (effective weight / 100) along the path
```

The share comes from `iter_test_shares` in
`autograder/models/contracts/scoring.py`, the same effective weights used for
grading: sibling ratios scaled to 100, all-zero siblings shared equally and a
mixed holder split once by `subjects_weight`. Within each category, criteria are
sorted by `diff_score` (descending); ties keep the canonical criterion order. For
the base category the impacts sum to the points lost.

## Example

A base category with subject `Program` (weight 3) holding test `p`, and subject
`Quality` (weight 1, `subjects_weight` 60) holding subject `Imports` with test
`imports` plus direct test `artifact`, all scoring 0:

| Criterion | Share | diff_score |
|---|---|---|
| `p` | 0.75 | 75 |
| `imports` | 0.25 × 0.60 = 0.15 | 15 |
| `artifact` | 0.25 × 0.40 = 0.10 | 10 |

## Where it is used

`render_feedback` calls `find_focus` only when the definition enables feedback
(see [requested feedback](../pipeline/07-feedback.md)). Disabled feedback never
computes focus.
