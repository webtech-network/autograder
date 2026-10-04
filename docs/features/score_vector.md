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

Internal `ResultTree.iter_test_results()` yields `(criterion_id, TestResultNode)`
and `to_score_vector()` provides the same map. Missing or duplicate IDs raise an
error rather than silently overwriting an assessment. Deserialization preserves
IDs and evaluator identifiers.

The v1 outcome has one authoritative tree and no independent `score_vector`
wire field. Hosts can derive and index vectors for their own query requirements.
Failed grading has no authoritative tree or vector. Compare vectors alongside
exact definition provenance: unchanged IDs do not prove unchanged evaluator
parameters or weights across definition revisions.

Migration changes old keys such as `base/Quality/Imports` to explicitly authored
criterion IDs. Historical vectors without IDs are not automatically comparable
to v1 executions; offline migration must resolve identities deliberately.

See [Terminal outcomes](../contracts/OUTCOMES.md) and
[Baseline comparison](baseline_comparison.md).
