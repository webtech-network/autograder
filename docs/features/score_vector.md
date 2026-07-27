# Score Vector

**Status:** Implemented  
**Related:** [Focus Feature](focus_feature.md), [Result Tree](../architecture/result_tree.md)

---

## Overview

The **score vector** is a flat, path-keyed map of every test score produced by a grading execution. It is a denormalised projection of data already computed in the `ResultTree`, designed for longitudinal queries, progress tracking, and regression detection.

```json
{
  "base/code_quality/complexity/cyclomatic_complexity": 72.0,
  "base/code_quality/documentation/docstring_coverage": 88.0,
  "base/test_coverage/test_inclusion": 60.0,
  "bonus/architecture/design_pattern_usage": 95.0,
  "penalty/hygiene/code_duplication": 45.0
}
```

Keys are stable path strings in `category/subject/.../test_name` format. Values are raw test scores (0–100). The vector is consistent across all executions of the same criteria config version.

---

## Motivation

The `result_tree` is a deeply nested JSON structure. To extract a single test score from it, a consumer must recursively traverse the tree, find the right node, and extract the score. This is expensive and fragile, especially when repeated across dozens of submissions for trend analysis.

The score vector flattens this into a single-level dict, enabling:

- **Direct SQL queries** against individual test scores without application-side parsing
- **Cross-submission comparison** by diffing two score vectors
- **Regression detection** by comparing the same key across submissions
- **Group-level analytics** (averages, distributions) via standard SQL aggregations

---

## How It Works

### Tree Traversal: `ResultTree.iter_test_results()`

The `iter_test_results()` method on `ResultTree` walks the full hierarchy:

```
Root → Categories (base, bonus, penalty) → Subjects (recursive) → Tests
```

For each test leaf node, it yields a `(path, TestResultNode)` tuple where the path encodes the full ancestry:

```python
for path, node in result_tree.iter_test_results():
    print(f"{path}: {node.score}")
# base/code_quality/complexity/cyclomatic_complexity: 72.0
# base/code_quality/documentation/docstring_coverage: 88.0
# ...
```

### Score Vector: `ResultTree.to_score_vector()`

A thin wrapper that calls `iter_test_results()` and returns the flat dict:

```python
vector = result_tree.to_score_vector()
# {"base/code_quality/complexity/cyclomatic_complexity": 72.0, ...}
```

### Storage

The score vector is stored as a nullable JSON column (`score_vector`) on the `submission_results` table. It is populated automatically during `_persist_success` in the grading service. Failed or interrupted pipeline executions have `score_vector = NULL`.

### API

The `score_vector` field is included in:
- `SubmissionResponse` (list view)
- `SubmissionDetailResponse` (detail view)
- `ExternalResultCreate` (external result ingestion)

---

## Score Vector vs Focus

Both are derived from `ResultTree`, but they serve different purposes:

| | Focus | Score Vector |
|---|---|---|
| **Purpose** | Guide immediate feedback | Enable comparison and trend queries |
| **Includes passing tests** | No | Yes |
| **Sorted** | Yes, by impact | No |
| **Key** | None (ordered list) | Stable path string |
| **Weight-aware** | Yes | No — raw test score only |
| **Consumer** | Feedback renderer | History/trend/regression queries |

---

## Version Safety

Score vectors are only comparable across submissions graded under the **same `grading_config_id` and config `version`**. If the criteria config changes (tests added, subjects renamed), the path keys change, making cross-version vectors incompatible.

Consumers performing longitudinal queries must filter by both `grading_config_id` and `version`.

---

## SQL Query Examples

**Track one metric over time:**
```sql
SELECT
    submitted_at,
    (score_vector->>'base/code_quality/complexity/cyclomatic_complexity')::float AS score
FROM submission_results
JOIN submissions ON submissions.id = submission_results.submission_id
WHERE submissions.external_user_id = 'user-123'
  AND submissions.grading_config_id = 42
ORDER BY submitted_at;
```

**Detect regressions between two submissions:**
```sql
SELECT key, prev.value::float AS before, curr.value::float AS after
FROM jsonb_each_text(
    (SELECT score_vector FROM submission_results WHERE id = :prev_id)
) prev(key, value)
JOIN jsonb_each_text(
    (SELECT score_vector FROM submission_results WHERE id = :curr_id)
) curr(key, value) USING (key)
WHERE curr.value::float < prev.value::float;
```

**Compute class average for a specific test:**
```sql
SELECT
    AVG((score_vector->>'base/code_quality/complexity/cyclomatic_complexity')::float)
FROM submission_results sr
JOIN submissions s ON s.id = sr.submission_id
WHERE s.grading_config_id = 42
  AND s.submitted_at > NOW() - INTERVAL '30 days';
```
