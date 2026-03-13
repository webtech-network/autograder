# Focus Feature

## Overview

The Focus feature organizes all executed tests based on their impact on the final score. This helps identify which tests had the most significant effect on the student's grade, making it easier to understand where the student struggled the most.

## What is Focus?

Focus is a data structure that ranks tests by their "diff_score" - the number of points deducted from the final score due to that specific test failing or performing poorly. Tests are organized into three categories:

1. **Base**: Tests that contribute to the base score
2. **Penalty**: Tests that apply penalties (if configured)
3. **Bonus**: Tests that provide bonus points (if configured)

Within each category, tests are sorted by their impact (diff_score) in descending order, so the most impactful tests appear first.

## Data Structure

```json
{
  "base": [
    {
      "test_result": {
        "name": "test_name",
        "score": 85.0,
        "weight": 20.0,
        "status": "PARTIAL",
        ...
      },
      "diff_score": 3.0
    },
    ...
  ],
  "penalty": [...],  // Optional
  "bonus": [...]     // Optional
}
```

### Fields

- **test_result**: The complete test result node with all details (name, score, weight, status, etc.)
- **diff_score**: The actual points deducted from the final score (0-100 scale) by this test

## How It Works

The Focus service calculates the impact of each test by considering:

1. **Test Score**: How well the student performed on that specific test (0-100)
2. **Test Weight**: The importance of that test relative to its siblings
3. **Cumulative Multiplier**: The cascading effect of parent weights through the tree structure

The formula for impact calculation:
```
diff_score = (100 - test_score) * (test_weight / 100) * cumulative_multiplier
```

## Integration

### Pipeline Integration

The Focus step is automatically executed when feedback generation is enabled. It runs after the GRADE step and before the FEEDBACK step:

```
LOAD_TEMPLATE → BUILD_TREE → PRE_FLIGHT → GRADE → FOCUS → FEEDBACK
```

### Storage

The Focus object is stored in the `submission_results` table as a JSON field alongside:
- `result_tree`: The complete test execution tree
- `feedback`: Generated feedback text
- `pipeline_execution`: Pipeline execution summary

### API Response

When retrieving submission results via the API, the Focus data is included in the response:

```http
GET /api/v1/submissions/{submission_id}
```

Response:
```json
{
  "id": 123,
  "status": "completed",
  "final_score": 85.5,
  "result_tree": {...},
  "focus": {
    "base": [...],
    "penalty": null,
    "bonus": null
  },
  "feedback": "...",
  ...
}
```

## Use Cases

### 1. Feedback Generation
The Focus data helps AI feedback generators prioritize which tests to discuss in detail, focusing on the tests that had the most significant impact on the score.

### 2. Student Analytics
Instructors can quickly identify which concepts or test categories caused the most trouble for students across multiple submissions.

### 3. Debugging
During development, Focus helps verify that weight calculations and score propagation are working correctly throughout the criteria tree.

## Example

Consider a submission with the following tests:
- Test A: score=50, weight=30, parent_weight=100 → diff_score = 15.0
- Test B: score=90, weight=20, parent_weight=100 → diff_score = 2.0
- Test C: score=0, weight=10, parent_weight=50 → diff_score = 5.0

The Focus base array would be ordered as:
```
[Test A (15.0), Test C (5.0), Test B (2.0)]
```

This immediately shows that Test A had the most significant impact on the final score, followed by Test C, then Test B.

## Database Migration

To add Focus support to an existing database, run:

```bash
make db-upgrade
```

Or manually:
```bash
cd /home/raspiestchip/PycharmProjects/autograder
alembic -c web/alembic.ini upgrade head
```

The migration adds a nullable `focus` JSON column to the `submission_results` table.

## Technical Details

### Classes

- **Focus** (`autograder/models/dataclass/focus.py`): Main dataclass holding base, penalty, and bonus test lists
- **FocusedTest** (`autograder/models/dataclass/focus.py`): Wrapper combining a test result with its calculated impact
- **FocusService** (`autograder/services/focus_service.py`): Service that calculates impact scores and generates Focus objects
- **FocusStep** (`autograder/steps/focus_step.py`): Pipeline step that executes the focus service

### Serialization

Both Focus and FocusedTest implement `to_dict()` methods for JSON serialization, recursively converting nested TestResultNode objects.

