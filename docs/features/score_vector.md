# Criterion score vectors

A score vector projects the canonical result tree to `{criterion_id: score}`.
IDs come from grading-definition test `id` fields; names and subject names are
presentation. Two criteria can share a display name without losing either score,
and renaming or regrouping a criterion does not change its identity.

```python
from autograder.models.contracts.outcome import outcome_score_vector

vector = outcome_score_vector(execution.outcome)  # completed outcomes only
# {"imports": 100.0, "algorithm": 75.0}
```

Vectors are derived only from the canonical outcome tree. The former internal
`ResultTree.iter_test_results()` and `to_score_vector()` helpers are removed.
Missing or duplicate IDs fail outcome validation rather than silently
overwriting an assessment. Deserialization preserves IDs and evaluator
identifiers.

The v1 outcome has one authoritative tree and no independent `score_vector`
wire field. Hosts can derive and index vectors for their own query requirements.
Failed grading has no authoritative tree or vector. Unchanged IDs do not prove
unchanged evaluator parameters or weights across definition revisions; use
`compare_outcomes`, which checks both definitions, instead of diffing raw vectors.
The `submission_results.score_vector` database column is unused legacy storage.

Migration changes old keys such as `base/Quality/Imports` to explicitly authored
criterion IDs. Historical vectors without IDs are not automatically comparable
to v1 executions; offline migration must resolve identities deliberately.

See [Terminal outcomes](../contracts/OUTCOMES.md) and
[Baseline comparison](baseline_comparison.md).
