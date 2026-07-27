# Baseline Comparison

**Status:** Implemented  
**Related:** [Score Vector](score_vector.md), [Focus Feature](focus_feature.md), [Core Structures](../architecture/core_structures.md)

---

## Overview

**Baseline Comparison** allows the autograder to compare two grading results produced from the same criteria config version and return a structured delta (`ComparisonResult`).

This is a post-pipeline feature executed in the web layer after `pipeline.run()`. It does not trigger a second pipeline execution or run code in a sandbox — it operates entirely on the stored `result_tree` structures.

```json
{
  "score_delta": 15.0,
  "improved": true,
  "test_deltas": [
    {
      "path": "base/code_quality/cyclomatic_complexity",
      "status": "improved",
      "baseline_score": 60.0,
      "head_score": 90.0,
      "delta": 30.0
    },
    {
      "path": "base/code_quality/docstring_coverage",
      "status": "regressed",
      "baseline_score": 100.0,
      "head_score": 75.0,
      "delta": -25.0
    },
    {
      "path": "base/new_module/unit_tests",
      "status": "introduced",
      "baseline_score": null,
      "head_score": 100.0,
      "delta": null
    }
  ]
}
```

---

## Motivation

The pipeline produces an absolute score (0–100) and a result tree. For gamification, regression alerts, and progress tracking, knowing the absolute score alone is insufficient. Callers need to answer questions like:

- *"Did this submission improve over the student's previous attempt?"*
- *"Which specific tests regressed since the last commit?"*
- *"How many points were gained or lost overall?"*

The caller provides the `baseline_result_tree` from a previous submission, and the autograder computes the comparison alongside the new grading execution.

---

## Data Structure: `ComparisonResult` & `TestDelta`

### `TestDelta.status` Values

| Status | Meaning |
|---|---|
| `improved` | `delta > 0` (score increased) |
| `regressed` | `delta < 0` (score decreased) |
| `unchanged` | `delta == 0` (score stayed the same) |
| `introduced` | Path present in head, missing in baseline (new test/file) |
| `removed` | Path present in baseline, missing in head (removed test/file) |

---

## How It Works

1. Caller submits code with optional `baseline_result_tree` in `SubmissionCreate`.
2. Pipeline grades current submission, producing `head_tree` (`ResultTree`).
3. If `baseline_result_tree` is provided:
   - Deserialises baseline into a `ResultTree` using `ResultTree.from_dict()`.
   - Calls `ResultComparator.compare(baseline=baseline_tree, head=head_tree)`.
   - Attaches `ComparisonResult` to `GradingResult.comparison`.
4. Persists `comparison` JSON column in `submission_results` table.
5. Returns `comparison` object in `SubmissionResponse` / `SubmissionDetailResponse`.

---

## API Usage

### Creating a Submission with Baseline

```http
POST /api/v1/submissions
Content-Type: application/json

{
  "external_assignment_id": "assignment-01",
  "external_user_id": "user-123",
  "username": "student",
  "files": [
    { "filename": "main.py", "content": "print('hello')" }
  ],
  "baseline_result_tree": {
    "final_score": 75.0,
    "children": { ... }
  }
}
```

---

## Domain Agnosticism

`ResultComparator` is domain-agnostic. It knows nothing about git, commits, or LMS platforms. It simply compares two `ResultTree` objects.
