# Optional result comparison

`ResultComparator.compare(baseline, head)` compares two internal `ResultTree`
instances without regrading either submission. It joins their criterion IDs,
computes overall score change, and reports improved/regressed/unchanged criteria
plus introduced/removed criteria. Its existing `path` field now means criterion
ID, never a display-name path.

```python
from autograder.models.contracts.outcome import ComparisonOutcome, validate_outcome
from autograder.services.result_comparator import ResultComparator

comparison = ResultComparator.compare(baseline_tree, head_tree)
wire = completed_outcome.model_dump(mode="json")
wire["comparison"] = ComparisonOutcome(
    status="completed", content=comparison.to_dict()
).model_dump(mode="json")
enriched = validate_outcome(wire)
```

A hosting adapter owns selecting a trusted baseline and deciding whether the
comparison is meaningful across revisions. The engine does not fetch baselines,
rerun evaluations, or infer baseline identity from submission usernames.
The current HTTP contract has no opaque `baseline_result_tree` input. A hosting
adapter must choose and verify a trusted baseline before supplying comparison
content.

Comparison is disabled by default. An adapter may supply completed comparison
content, or mark optional comparison failed with a safe structured error while
preserving completed grading. Delta scores must be finite and consistent with
their baseline/head scores and status; criterion IDs must be unique. Renames and
duplicate display labels cannot reidentify criteria.

```json
{
  "status": "completed",
  "content": {
    "score_delta": 25,
    "improved": true,
    "test_deltas": [{
      "path": "algorithm",
      "status": "improved",
      "baseline_score": 50,
      "head_score": 75,
      "delta": 25
    }]
  },
  "error": null
}
```

See [Terminal outcomes](../contracts/OUTCOMES.md) and
[Criterion score vectors](score_vector.md).
