# Grading Engine

## Overview

The grading engine turns a compiled `CriteriaTree` (the rubric) and a student
submission into the canonical assessed tree, `ResultOutcomeTree`: a scored mirror
of the criteria with every result stored as data. It is the domain behind the
[Assess](../pipeline/04.5-ai-batch.md) and [Grade](../pipeline/05-grade.md)
operations.

The executable definition and the assessed result stay distinct:

| | Executable definition | Assessed result |
|---|---|---|
| Model | `CriteriaTree` → `CategoryNode` / `SubjectNode` / `TestNode` | `ResultOutcomeTree` → `CategoryOutcome` / `SubjectOutcome` / `TestOutcome` |
| Holds | trusted evaluator instance, frozen canonical parameters, authored weights | criterion ID, evaluator ID, label, file target, canonical parameters, effective weight, score, report |
| Built by | `compile_definition` / `compile_snapshot` | `grade(criteria, results)`, once per run |

A result never references a `TestNode` or evaluator, so a stored or attested tree
can be read, compared and re-validated without recreating evaluators, and its
JSON round trip (`model_dump(mode="json")` → `ResultOutcomeTree.model_validate`)
preserves every field, including file targets.

---

## Assessment, then aggregation

Grading has two explicit calls with one value between them:

```python
results = assess_criteria(criteria_tree, submission, session=session, ai=provider)  # {criterion_id: TestResult}
tree = grade(criteria_tree, results)                                                  # ResultOutcomeTree
```

`assess_criteria` (`autograder/services/assessment.py`) walks the compiled tree
once in the canonical order and prepares every criterion:

```python
evaluation = EvaluationInput(files=tuple(select_files(test, ...)), language=submission.language,
                             locale=submission.locale,
                             session=session if declares_execution else None)
result = test.test_function.execute(evaluation, **thaw(test.parameters))   # ordinary
results.update(assess_many(ai_criteria, provider, ...))                     # all AI criteria, one call
```

Key details:
- **One call shape**: `execute(self, evaluation, *, <configuration>)`. Keyword-only
  parameters are exactly the normalized contract fields; the signature is
  validated when a template is registered or compiled.
- **File targeting**: `evaluation.files` holds the files selected by the
  [file contract](../contracts/FILES.md), each with its metadata and changed lines.
- **Language**: `evaluation.language` is the selected submission language. The I/O
  evaluators resolve their own `program_command`; the engine interprets no
  parameter names.
- **Session**: only evaluators declaring `sandbox_execution` or `http_network`
  receive the execution session. AI results never reach ordinary evaluators.
- **Isolation**: every call receives a fresh copy of the frozen canonical parameters.

Each evaluator returns a frozen `TestResult(test_name, score, report)` with a
finite score in 0–100. `test_name` is informational; the tree takes identity,
evaluator ID, label, file target and parameters from the compiled criterion.

`grade` (`autograder/services/grading.py`) executes no evaluator. It places each
criterion's result under its compiled holder with its effective weight, computes
holder and final scores and validates the result as a `ResultOutcomeTree`. The
pipeline then applies `verify_outcome_tree`, the same structural check used for
externally attested outcomes.

---

## One scoring definition

`autograder/models/contracts/scoring.py` is the only definition of traversal,
effective weights and score arithmetic. Grading, outcome validation,
definition-versus-outcome verification, focus selection and comparison all use it.

- **Traversal** (`iter_tests`): categories in base, bonus, penalty order; within a
  holder, nested subjects before direct tests. Assessment executes in this order.
- **Effective weights** (`child_weights`, `normalized_sibling_weights`): sibling
  weights are ratios scaled to 100; all-zero siblings share equally; a holder with
  both subjects and tests splits 100 by `subjects_weight` (subjects get
  `subjects_weight`, tests the rest).
- **Holder score** (`holder_score`): the weighted mean of the children's unrounded
  scores.
- **Final score** (`final_score`): `base + bonus/100 * bonus_cap - (100 - penalty)/100 * penalty_cap`,
  clamped to 0–100.
- **Rounding** (`report_score`): every reported score is rounded to two decimals;
  effective weights are not rounded.
- **Shares** (`iter_test_shares`): the product of a test's and its ancestors'
  effective weights / 100 and the category weight / 100. `(100 - score) * share` is
  the points a criterion cost, which focus uses to order feedback.

```
subjects_weight = 70
├── Subjects group gets 70, split by subject weight ratios
└── Tests group gets 30, split by test weight ratios
```

Outcome validation recomputes holder and root scores from the reported values
independently of the producer (tolerances 0.011 and 0.021 absorb rounding).

---

## AI Test Execution

Some templates include AI-powered tests that delegate evaluation to an LLM. These tests extend the `AiTestFunction` ABC (instead of `TestFunction` directly) and implement a `build_prompt()` method that describes what the AI should evaluate.

Adding one changes only its prompt builder, parameter contract, registration
and tests. `assess_criteria` gives every selected AI criterion to
`assess_many`, which builds the prompts, makes **one** provider call for the
group and returns results keyed by criterion ID; a single AI criterion is a
group of one. `assess_many` validates exact coverage: unknown, duplicate,
missing and invalid provider answers fail the required grade (no retry, no
zero). The merged results reach the grader like any other result; AI evaluators
are never executed individually, ordinary evaluators never receive AI results,
and the grader has no AI parameter. See [assessment](../pipeline/04.5-ai-batch.md).

---

## Derived views

All derive from the authoritative assessed tree and are keyed by criterion ID,
so repeated labels or labels containing slashes never collide:

- `score_vector(tree)` / `outcome_score_vector(outcome)` → `{criterion_id: score}`.
- `find_focus(tree)` → criteria per category ordered by points lost (used only for requested feedback).
- The default feedback report (learning resources link criterion IDs).
- `compare(baseline_tree, head_tree)` → the contract's `ComparisonContent`.

---

## Source Files

| File | Contents |
|------|----------|
| `autograder/services/assessment.py` | `assess_criteria`, `assess_many`: criterion preparation, evaluator execution, the AI batch |
| `autograder/services/grading.py` | `grade`: builds the canonical `ResultOutcomeTree` once |
| `autograder/models/contracts/scoring.py` | traversal, effective weights, score arithmetic, rounding |
| `autograder/models/contracts/verification.py` | `verify_outcome_tree`: definition-versus-outcome structure |
| `autograder/models/contracts/outcome.py` | `ResultOutcomeTree` and the terminal outcome models |
| `autograder/models/criteria_tree.py` | `CriteriaTree`, `CategoryNode`, `SubjectNode`, `TestNode` |
| `autograder/models/dataclass/test_result.py` | `TestResult`: an evaluator's return value |
| `autograder/models/contracts/comparison.py` | `compare_outcomes`: pure ID-joined comparison of two canonical outcomes ([Baseline Comparison](baseline_comparison.md)) |
| `autograder/template_library/input_output.py` | I/O evaluators, including `program_command` selection (see [Program Commands](program_commands.md)) |
