# Grading Engine

## Overview

The grading engine is the core subsystem behind the [Grade pipeline step](../pipeline/05-grade.md). It takes a `CriteriaTree` (the rubric) and a student submission, executes every test function in the tree, and produces a `ResultTree` — a scored mirror of the criteria tree with actual results, reports, and aggregated scores at every level.

This document covers the engine's internal mechanics: how it traverses the tree, executes tests, resolves files, handles weights, and calculates scores.

---

## Assessment, then aggregation

Grading has two explicit calls with one value between them:

```python
results = assess_criteria(criteria_tree, submission, session=session, ai=provider)  # {criterion_id: TestResult}
result_tree = GraderService().grade_from_tree(criteria_tree, results)
```

`assess_criteria` (`autograder/services/assessment.py`) walks the compiled tree
once, nested subjects before a holder's direct tests, and prepares every criterion:

```python
evaluation = EvaluationInput(files=tuple(select_files(test, ...)), language=submission.language,
                             locale=submission.locale,
                             session=session if declares_execution else None)
result = test.test_function.execute(evaluation, **thaw(test.parameters))   # ordinary
results.update(assess_many(ai_criteria, provider, ...))                     # all AI criteria, one call
```

`GraderService.grade_from_tree()` then processes the criteria tree top-down,
placing each criterion's result and balancing weights:

```
CriteriaTree
├── base (CategoryNode)    ──▶ process_category() ──▶ CategoryResultNode
├── bonus (CategoryNode)   ──▶ process_category() ──▶ CategoryResultNode
└── penalty (CategoryNode) ──▶ process_category() ──▶ CategoryResultNode
```

Key details:
- **One call shape**: `execute(self, evaluation, *, <configuration>)`. Keyword-only
  parameters are exactly the normalized contract fields; the signature is
  validated when a template is registered or compiled.
- **File targeting**: `evaluation.files` holds the files selected by the
  [file contract](../contracts/FILES.md), each with its metadata and changed lines.
- **Language**: `evaluation.language` is the selected submission language. The I/O
  evaluators resolve their own `program_command`; the grader interprets no
  parameter names.
- **Session**: only evaluators declaring `sandbox_execution` or `http_network`
  receive the execution session. AI results never reach ordinary evaluators.
- **Isolation**: every call receives a fresh copy of the frozen canonical parameters.

Each `TestFunction.execute()` returns a `TestResult` with:
- `score` (0–100)
- `report` (human-readable explanation)
- `parameters` (optional, echoed back for transparency)

---

## Weight Balancing

Weights determine how much each node contributes to its parent's score. The engine enforces that sibling weights always sum to 100 at every level.

### Sibling Balancing

The `__balance_nodes()` method normalizes weights to a target total based on a factor:

```python
def __balance_nodes(self, nodes, factor):
    target_total = 100.0 * factor
    current_sum = sum(node.weight for node in nodes)
    
    if current_sum == 0:
        equal_weight = target_total / len(nodes)
        for node in nodes:
            node.weight = equal_weight
    else:
        scale_factor = target_total / current_sum
        for node in nodes:
            node.weight *= scale_factor
```

- If all weights are zero, they're distributed equally to sum to `100 * factor`.
- If they don't sum to the target total, they're scaled proportionally.

### Subject/Test Split

When a node contains both subjects and direct tests, the `subjects_weight` field determines the split:

```
subjects_weight = 70
├── Subjects group gets factor = 0.70
└── Tests group gets factor = 0.30
```

Each group's weights are balanced independently within their respective factor. This means subjects compete with subjects, and tests compete with tests, with the `subjects_weight` controlling the ratio between the two groups.

If a node has only subjects or only tests, the factor is 1.0 (no split needed).

---

## Score Calculation

After the entire tree is processed, `ResultTree.calculate_final_score()` aggregates scores bottom-up through the `RootResultNode`:

```
final_score = base_score + bonus_contribution - penalty_deduction
```

At each level, the score is a weighted average:

```python
# For a subject or category:
score = sum(child.score * child.weight / 100 for child in children)
```

The `RootResultNode.calculate_score()` combines the three categories:
- **Base**: The primary score (0–100 scale, weighted by `base.weight`)
- **Bonus**: Added on top (e.g., weight=10 means up to 10 extra points)
- **Penalty**: Subtracted (e.g., weight=-20 means up to 20 points deducted)

---

## File Targeting

The `get_file_target()` method resolves which submission files a test should receive:

```python
def get_file_target(self, test_node: TestNode):
    if not test_node.file_target or not self.__submission_files:
        return None
    target_files = []
    for file_name in self.__submission_files:
        if file_name in test_node.file_target:
            target_files.append(self.__submission_files[file_name])
    return target_files
```

This allows tests to operate on specific files (e.g., a `has_tag` test targeting only `index.html`) rather than the entire submission. If no `file_target` is specified, the test receives `None` and is expected to work with the sandbox or handle files internally.

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

## Result Tree Structure

The output `ResultTree` mirrors the `CriteriaTree` but with actual scores:

```
ResultTree
├── root: RootResultNode
│   ├── base: CategoryResultNode
│   │   ├── subjects: [SubjectResultNode, ...]
│   │   │   ├── tests: [TestResultNode, ...]
│   │   │   └── subjects: [SubjectResultNode, ...]
│   │   └── tests: [TestResultNode, ...]
│   ├── bonus: CategoryResultNode (optional)
│   └── penalty: CategoryResultNode (optional)
├── template_name: str (optional)
└── metadata: dict
```

Each `TestResultNode` contains:
- `name` — Test identifier
- `score` — Achieved score (0–100)
- `report` — Human-readable result explanation
- `parameters` — Test parameters used
- `file_target` — The criterion's explicit file target (results never retain live
  compiled tree nodes)

The `ResultTree` also provides utility methods:
- `get_all_test_results()` — Flat list of all test result nodes
- `get_failed_tests()` — Tests with score < 100
- `get_passed_tests()` — Tests with score = 100
- `to_dict()` — Full serialization with summary statistics

---

## Source Files

| File | Contents |
|------|----------|
| `autograder/services/assessment.py` | `assess_criteria`, `assess_many` — criterion preparation, evaluator execution, the AI batch |
| `autograder/services/grader/grader_service.py` | `GraderService` — aggregates ID-keyed results into a result tree |
| `autograder/services/grader/criteria_grader.py` | `SubmissionGrader` — tree traversal and weight balancing (no evaluator calls) |
| `autograder/models/result_tree.py` | `ResultTree`, `RootResultNode`, `CategoryResultNode`, `SubjectResultNode`, `TestResultNode` |
| `autograder/models/criteria_tree.py` | `CriteriaTree`, `CategoryNode`, `SubjectNode`, `TestNode` |
| `autograder/models/dataclass/test_result.py` | `TestResult` — individual test execution output |
| `autograder/services/command_resolver.py` | `CommandResolver` — multi-language command resolution |
