# Grading Engine

## Overview

The grading engine is the core subsystem behind the [Grade pipeline step](../pipeline/05-grade.md). It takes a `CriteriaTree` (the rubric) and a student submission, executes every test function in the tree, and produces a `ResultTree` — a scored mirror of the criteria tree with actual results, reports, and aggregated scores at every level.

This document covers the engine's internal mechanics: how it traverses the tree, executes tests, resolves files, handles weights, and calculates scores.

---

## Tree Traversal

The `GraderService.grade_from_tree()` method is the entry point. It processes the criteria tree top-down:

```
CriteriaTree
├── base (CategoryNode)    ──▶ process_category() ──▶ CategoryResultNode
├── bonus (CategoryNode)   ──▶ process_category() ──▶ CategoryResultNode
└── penalty (CategoryNode) ──▶ process_category() ──▶ CategoryResultNode
```

Each `process_category()` call delegates to `__process_holder()`, a generic method that handles both `CategoryNode` and `SubjectNode` since they share the same structure (subjects + tests + optional `subjects_weight`).

For each holder node:
1. Process all child **subjects** recursively → list of `SubjectResultNode`
2. Process all child **tests** → list of `TestResultNode`
3. Balance weights for each group
4. Return the corresponding result node

---

## Test Execution

When the engine reaches a `TestNode`, it calls `process_test()`:

```python
def process_test(self, test: TestNode) -> TestResultNode:
    file_target = self.get_file_target(test)
    test_params = test.parameters or {}
    if self._submission_language:
        test_params['__submission_language__'] = self._submission_language

    test_result = test.test_function.execute(
        files=file_target, sandbox=self._sandbox, **test_params
    )
    return TestResultNode(
        name=test.name,
        test_node=test,
        score=test_result.score,
        report=test_result.report,
        parameters=test_result.parameters,
    )
```

Key details:
- **File targeting**: If the `TestNode` specifies a `file_target`, only matching submission files are passed to the test function. Otherwise, `None` is passed and the test operates on the sandbox or all files.
- **Language injection**: The submission language is injected as `__submission_language__` into the test parameters, enabling multi-language command resolution inside test functions (e.g., choosing `python3 main.py` vs `java Main`).
- **Sandbox**: The sandbox container (if any) is passed to every test function. Templates that require sandbox execution (like `input_output`) use it to run student code.

Each `TestFunction.execute()` returns a `TestResult` with:
- `score` (0–100)
- `report` (human-readable explanation)
- `parameters` (optional, echoed back for transparency)

---

## Weight Balancing

Weights determine how much each node contributes to its parent's score. The engine enforces that sibling weights always sum to 100 at every level.

### Sibling Balancing

The `__balance_nodes()` method normalizes weights:

```python
def __balance_nodes(self, nodes, factor):
    total_weight = sum(node.weight for node in nodes) * factor
    if total_weight == 0:
        equal_weight = 100.0 / len(nodes)
        for node in nodes:
            node.weight = equal_weight
    elif total_weight != 100:
        scale_factor = 100.0 / total_weight
        for node in nodes:
            node.weight *= scale_factor
```

- If all weights are zero, they're distributed equally.
- If they don't sum to 100 (after applying the factor), they're scaled proportionally.

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

## AI Executor Integration

Some templates use an `AiExecutor` for batch AI-powered test execution. After the tree traversal completes, the engine checks if the first test has an attached executor and calls `executor.stop()` to flush any pending AI batch requests:

```python
first_test = self.__find_first_test(criteria_tree.base)
if first_test and hasattr(first_test, "test_function"):
    test_func = first_test.test_function
    if hasattr(test_func, "executor") and test_func.executor:
        test_func.executor.stop()
```

This is a post-processing step that ensures all AI-batched results are resolved before the `ResultTree` is returned.

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
- `test_node` — Reference back to the original `TestNode`

The `ResultTree` also provides utility methods:
- `get_all_test_results()` — Flat list of all test result nodes
- `get_failed_tests()` — Tests with score < 100
- `get_passed_tests()` — Tests with score = 100
- `to_dict()` — Full serialization with summary statistics

---

## Source Files

| File | Contents |
|------|----------|
| `autograder/services/grader_service.py` | `GraderService` — tree traversal, test execution, weight balancing |
| `autograder/models/result_tree.py` | `ResultTree`, `RootResultNode`, `CategoryResultNode`, `SubjectResultNode`, `TestResultNode` |
| `autograder/models/criteria_tree.py` | `CriteriaTree`, `CategoryNode`, `SubjectNode`, `TestNode` |
| `autograder/models/dataclass/grade_step_result.py` | `GradeStepResult` — wrapper for final score + result tree |
| `autograder/models/dataclass/test_result.py` | `TestResult` — individual test execution output |
| `autograder/services/command_resolver.py` | `CommandResolver` — multi-language command resolution |
