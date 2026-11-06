# Scores: weights, bonus and penalty

This page is the one description of how a definition turns criterion results
into the final score. Every host computes it the same way, and the student
report shows the same numbers.

## From criteria to a score

1. **Each criterion scores 0 to 100.** Most evaluators give 0 or 100; some give
   partial credit, such as "found 1 of 2 required methods" scoring 50.
2. **A group scores the weighted average of its members.** Siblings' weights
   are ratios: 80 and 20 mean the same as 4 and 1. A member with weight 0
   still runs, and its result is reported, but it does not count; if every
   sibling has weight 0, they count equally. A criterion without a `weight`
   weighs 100.
3. **A group can hold both subjects and criteria.** Then `subjects_weight`
   (0 to 100) says how much of the group the subjects make up together; its
   own criteria make up the rest.
4. **`base` scores 0 to 100.** Its weight is always 100.
5. **`bonus` and `penalty` move the base score.** Their `weight` is the most
   points they can move it:

    ```text
    final = base score
          + bonus score / 100 × bonus weight
          − (100 − penalty score) / 100 × penalty weight
    ```

    and the result is kept between 0 and 100.

Reported scores are rounded to two decimals. A category you leave out simply
contributes nothing.

## Penalty

**A penalty criterion scores 100 when the student complied.** Write it as the
rule the student must follow, never as the mistake you are looking for. The
penalty then deducts only the shortfall: a criterion scoring 100 deducts
nothing, one scoring 0 deducts its full share of the penalty weight.

| Rule | Evaluator that scores 100 when it is followed |
| --- | --- |
| Do not import `os` | `forbidden_import` with `"forbidden_imports": ["os"]` |
| Do not call `eval` | `forbidden_keyword` with `"forbidden_keywords": ["eval_call"]` |
| No inline styles | `check_no_inline_styles` |
| No `<marquee>` | `has_forbidden_tag` with `"tag": "marquee"` |

The [evaluator reference](../reference/evaluators.md) marks such checks
"Passes when absent". A presence check in `penalty`, such as `has_tag` with
`"tag": "marquee"`, inverts the rule: it would deduct points from every
student who *avoided* the tag.

An ordinary criterion can be a penalty too: `dont_fail` in `penalty` deducts
points when the program crashes.

## Bonus

A bonus criterion adds its share of the bonus weight as it is earned: a
bonus of weight 10 with one criterion scoring 50 adds 5 points. Extra credit
cannot lift a score above 100, so a bonus helps a student who lost base points.

## A worked example

The tutorial's [web page](tutorial.md#2-a-web-page) graded on its bad
submission:

<!-- worked-example: examples/tutorial/web-page/definition.json -->
| Criterion `id` | Where it is | Score |
| --- | --- | --- |
| `main-heading` | base › HTML structure (40) | 100 |
| `semantic-tags` | base › HTML structure (40) | 40 |
| `image-alt` | base › HTML structure (40) | 0 |
| `stylesheet` | base › Styling (30) | 0 |
| `flexbox` | base › Styling (30) | 0 |
| `dom-updates` | base › Interactivity (30) | 50 |
| `responsive` | bonus (10) | 0 |
| `no-inline-styles` | penalty (10) | 0 |

* HTML structure: (100 + 40 + 0) / 3 = 46.67. Styling: 0. Interactivity: 50.
* Base: (46.67 × 40 + 0 × 30 + 50 × 30) / 100 = 33.67.
* Bonus: 0 / 100 × 10 = 0. Penalty: (100 − 0) / 100 × 10 = 10.

Final score: **23.67**

The good compiled solution earns everything, bonus included. The bonus cannot
lift it above 100:

<!-- worked-example: examples/tutorial/compiled/definition.json -->
| Criterion `id` | Where it is | Score |
| --- | --- | --- |
| `zero` | base | 100 |
| `five` | base | 100 |
| `ten` | base | 100 |
| `twenty` | bonus (10) | 100 |

100 + 100 / 100 × 10 = 110, kept at 100.

Final score: **100**

A group with both subjects and criteria splits by `subjects_weight`. In the
[nested example](https://github.com/webtech-network/autograder/blob/main/examples/definitions/nested-with-feedback.json)
the base holds the criterion `base-tests-0` and a subject holding
`nested-sum`, with `"subjects_weight": 25`:

<!-- worked-example: examples/definitions/nested-with-feedback.json -->
| Criterion `id` | Where it is | Score |
| --- | --- | --- |
| `base-tests-0` | base, its own criteria (75) | 100 |
| `nested-sum` | base › Nested/topic, the subjects (25) | 0 |

100 × 75 / 100 + 0 × 25 / 100 = 75.

Final score: **75**

## Designing a rubric

* Put what every student must achieve in `base`, extra credit in `bonus` and
  rules in `penalty`. Do not put required work in `bonus`.
* Name subjects after skills ("Handles bad input"), not after tools; the
  student report is organized by them.
* Weigh by importance, then grade a few real submissions and read the
  reports: [Test your rubric](testing.md).
* Keep criterion `id`s stable once students have submitted. Rewording `name`
  is safe; a new `id` is a new criterion in results and comparisons.
