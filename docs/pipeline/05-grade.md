# Step 5: Grade

## Purpose

The Grade step is the core of the autograder. It walks the `CriteriaTree`, executes every test function against the student's submission, collects scores, and produces a `ResultTree` — a scored mirror of the criteria tree. This is where the actual grading happens.

## How It Works

1. **Retrieve inputs** — The step reads the `Template` (from Load Template), the `CriteriaTree` (from Build Tree), and optionally the `SandboxContainer` (from Sandbox).
2. **Configure the grader** — If a sandbox exists, it's injected into the `GraderService`. The submission language is also set for command resolution in multi-language assignments.
3. **Tree traversal and execution** — The `GraderService.grade_from_tree()` method recursively processes the criteria tree:
   - For each **category** (base, bonus, penalty): process its subjects and direct tests.
   - For each **subject**: process nested subjects and tests, balancing weights.
   - For each **test**: execute the `TestFunction` with the submission files, sandbox, and parameters, producing a `TestResultNode` with a score (0–100) and a report.
4. **Score calculation** — `ResultTree.calculate_final_score()` aggregates scores bottom-up: test → subject → category → final score.
5. **Output** — A `GradeStepResult` containing the `final_score` and the full `ResultTree` is stored in the step result.

The grading engine is a complex subsystem with its own weight balancing, file targeting, and multi-language command resolution. For a deep explanation, see the **[Grading Engine](../features/grading_engine.md)** documentation.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Load Template** | The `Template` to check sandbox requirements |
| **Build Tree** | The `CriteriaTree` with embedded test functions |
| **Sandbox** | The `SandboxContainer` (only if template requires sandbox) |

## Input

| Source | Data |
|--------|------|
| Pipeline | `StepName.LOAD_TEMPLATE` → `Template` |
| Pipeline | `StepName.BUILD_TREE` → `CriteriaTree` |
| Pipeline | `StepName.SANDBOX` → `SandboxContainer \| None` (optional) |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `GradeStepResult` | Contains `final_score: float` and `result_tree: ResultTree` |
| `status` | `StepStatus.SUCCESS` | On successful grading |

## Score Calculation

Scores flow bottom-up through the tree:

```
TestResultNode (score: 0-100)
    └──▶ SubjectResultNode (weighted average of tests/sub-subjects)
            └──▶ CategoryResultNode (weighted average of subjects/tests)
                    └──▶ RootResultNode
                            final_score = base + bonus - penalty
```

When a node contains both subjects and direct tests, the `subjects_weight` field splits the score contribution. For example, `subjects_weight=70` means 70% of the node's score comes from subjects and 30% from direct tests.

Sibling weights are balanced to sum to 100 at each level. If they don't, the `GraderService` scales them proportionally.

## Failure Scenarios

- Template requires sandbox but none was created → `RuntimeError`.
- A test function raises an unhandled exception → the entire step fails with `StepStatus.FAIL`.
- CriteriaTree node missing `subjects_weight` when both subjects and tests exist → `ValueError`.

## Next Step

Once the results are in, the pipeline proceeds to **[Step 6: Focus](06-focus.md)** to rank results by impact.

---

## Source

`autograder/steps/grade_step.py` → `GradeStep`

`autograder/services/grader_service.py` → `GraderService`

`autograder/models/result_tree.py` → `ResultTree`, `RootResultNode`, `CategoryResultNode`, `SubjectResultNode`, `TestResultNode`

`autograder/models/dataclass/grade_step_result.py` → `GradeStepResult`
