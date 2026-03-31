# Step 6: Focus

## Purpose

The Focus step analyzes the grading results and ranks every test by its actual impact on the final score. Instead of just listing pass/fail, it answers the question: "Which failed tests cost the student the most points?" This ranking is essential for generating meaningful feedback that prioritizes the most impactful improvements.

## How It Works

The `FocusService` traverses the `ResultTree` produced by the Grade step and calculates a `diff_score` for each test — the number of points (on the 0–100 final score scale) that the test deducted.

The calculation accounts for the full weight chain from root to test:

```
diff_score = (100 - test_score) × (test_weight / 100) × cumulative_multiplier
```

The `cumulative_multiplier` is the product of all parent weight factors from the category root down to the test's parent subject. When a node has both subjects and direct tests (split via `subjects_weight`), the multiplier is split accordingly between the two groups.

Tests are processed per category (base, bonus, penalty) and sorted by `diff_score` in descending order within each category.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Grade** | The `ResultTree` containing all test scores and the weight hierarchy |

## Input

| Source | Data |
|--------|------|
| Pipeline | `StepName.GRADE` → `GradeStepResult.result_tree` |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `Focus` | Contains ranked test lists for base, penalty, and bonus categories |
| `status` | `StepStatus.SUCCESS` | On successful analysis |

## The Focus Data Structure

```python
@dataclass
class Focus:
    base: List[FocusedTest]              # Tests from base category, sorted by impact
    penalty: Optional[List[FocusedTest]] # Tests from penalty category (if configured)
    bonus: Optional[List[FocusedTest]]   # Tests from bonus category (if configured)

@dataclass
class FocusedTest:
    test_result: TestResultNode  # Full test result with score, report, parameters
    diff_score: float            # Points deducted from final score (0-100 scale)
```

## Example

Given a submission with these results:

| Test | Score | Weight | Parent Multiplier | diff_score |
|------|-------|--------|-------------------|------------|
| Test A | 50 | 30 | 1.0 | 15.0 |
| Test B | 90 | 20 | 1.0 | 2.0 |
| Test C | 0 | 10 | 0.5 | 5.0 |

The Focus base list would be: `[Test A (15.0), Test C (5.0), Test B (2.0)]`

This tells the student: "Fixing Test A would improve your score the most."

For a comprehensive explanation of the focus algorithm, data storage, and use cases, see the **[Focus Feature](../features/focus_feature.md)** documentation.

## Failure Scenarios

- Grade step result missing or malformed → exception caught, `StepStatus.FAIL`.
- Empty result tree → produces empty focus lists (not a failure).

## Next Step

After identifying the most impactful errors, the pipeline proceeds to **[Step 7: Feedback](07-feedback.md)** to generate student-facing reports.

---

## Source

`autograder/steps/focus_step.py` → `FocusStep`

`autograder/services/focus_service.py` → `FocusService`

`autograder/models/dataclass/focus.py` → `Focus`, `FocusedTest`
