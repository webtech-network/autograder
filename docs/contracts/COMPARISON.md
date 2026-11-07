# Baseline comparison of stored outcomes

Comparison answers one question: *how did this submission change relative to an
earlier stored submission of the same assignment?* It is a separate, read-only
use of two completed grades. It is never a grading stage, is never stored, and
never regrades or mutates either outcome.

## Consumer, owner and input contract

| Item | Decision |
| --- | --- |
| Consumer | Prisma (the upstream LMS) shows students and instructors progress between two stored submissions of one assignment. |
| HTTP owner | `GET /api/v1/submissions/{submission_id}/comparison?baseline_submission_id={id}`, authenticated with the integration bearer token. |
| Python owner | `autograder.compare_outcomes(baseline_outcome, head_outcome, baseline_definition, head_definition)`, a pure utility. |
| Input | Two stored submission IDs (HTTP) or two canonical `TerminalOutcome`s plus the exact normalized definitions they are bound to (Python). |
| Not accepted | Arbitrary baseline trees, score vectors or comparison content supplied by a caller. Vectors are always derived from the authoritative trees. |
| Retry | Call again. The result is a deterministic function of the stored data. |

`submission_id` is the *head* (newer) side. The operation reads both rows, their
bound definition snapshots and canonical outcomes, and returns the comparison.
Nothing is written. The grading outcome's own `comparison` enrichment remains
`disabled` for normal grading and is not changed by this operation.

## Compatibility rules

Both sides must be completed canonical outcomes whose definition hashes equal
the hash of the supplied (HTTP: stored) normalized definition snapshot. Criteria
are matched **only by criterion ID**. Display labels, subject names, order and
slashes never identify a criterion; duplicate labels and repeated evaluator
types stay distinct.

| Situation | `compatibility` | Overall `score_delta` | Criterion `status` | Criterion `delta` |
| --- | --- | --- | --- | --- |
| Same definition hash | `same_definition` | head − baseline | `improved` / `regressed` / `unchanged` | head − baseline |
| Different hash, criterion has identical evaluator type, normalized parameters, file target, effective weight and category | `cross_revision` | `null` | `improved` / `regressed` / `unchanged` | head − baseline |
| Different hash, identical type/parameters/target but changed effective weight or category | `cross_revision` | `null` | `reweighted` | head − baseline (0–100 criterion score) |
| Different hash, changed evaluator type, normalized parameters or file target | `cross_revision` | `null` | `redefined` | `null` (both scores shown) |
| Criterion only in head | either | — | `introduced` | `null` |
| Criterion only in baseline | `cross_revision` | — | `removed` | `null` |

*Effective weight* is the criterion's possible contribution to the final score in
points: the category's points (100 for base, `max_points` for bonus/penalty) multiplied by the
criterion's normalized share of that category, using the engine's sibling
ratio, all-zero-equal-share and `subjects_weight` rules. Proportionally rescaling
sibling weights (1:1 to 50:50) is not a reweight; regrouping into a renamed
subject with the same effective share is not a reweight. A change to one
sibling's weight changes the shares of all its siblings, so they are all
`reweighted`.

Any hash difference makes the overall score not comparable as a whole, even if
only preparation, languages or feedback changed, because those can
alter grading meaning outside individual criteria. `changed_definition_sections`
lists which top-level definition sections differ, and `explanation` states the
rule that applied. Per-criterion rows remain useful across revisions.

An outcome bound to a format 1.0 snapshot (graded before format 2.0) keeps that
snapshot: its hash is checked on the snapshot as stored, then the snapshot is
read through the offline converter's structural step, so its criteria join a
2.0 outcome's by ID. Such a comparison is `cross_revision` and lists
`schema_version` among the changed sections.

Externally attested and locally executed outcomes follow identical rules. Each
side reports `source`: `executed` (this server graded accepted source files) or
`attested` (an authenticated external host attestation; this server did not
execute it and does not claim to have verified it). In stored data an
attestation has no source files, whereas every accepted submission stores at
least one file.

## Errors

| Condition | HTTP | `detail.code` |
| --- | --- | --- |
| Missing or wrong bearer token | 401 (503 if the server has no token configured) | — |
| Head or baseline submission does not exist | 404 | — (`"Submission not found"` / `"Baseline submission not found"`) |
| Missing/invalid `baseline_submission_id` | 422 | FastAPI validation |
| Submissions belong to different grading configuration resources | 422 | `NOT_COMPARABLE` |
| A side is pending/processing, or its outcome is `failed` | 409 | `OUTCOME_NOT_COMPLETED` |
| A side has no bound definition snapshot or no canonical outcome (legacy history) | 409 | `LEGACY_UNVERIFIED` |
| Stored outcome does not match its stored snapshot (corruption) | 409 | `DEFINITION_MISMATCH` / `INVALID_OUTCOME` / `INVALID_DEFINITION` |

Error details for 409/422 are objects with `code`, `message` and, when one side is
responsible, `side` (`baseline` or `head`) and `submission_id`. Legacy records are
rejected rather than compared: correspondence is never guessed from display
names, old path-keyed score vectors or today's definition.

## Example

```http
GET /api/v1/submissions/42/comparison?baseline_submission_id=17
Authorization: Bearer <AUTOGRADER_INTEGRATION_TOKEN>
```

Submission 17 was executed against revision 1 (`greeting` labelled "Greeting",
score 60). Submission 42 was attested against revision 2, which renamed the
label to "Welcome" and added `farewell`:

```json
{
  "compatibility": "cross_revision",
  "baseline": {"submission_id": 17, "source": "executed", "execution_id": "4c0e…",
               "score": 60.0,
               "provenance": {"schema_version": "2.0", "definition_hash": "<64 hex, revision 1>",
                              "reference": "7", "revision": 1}},
  "head": {"submission_id": 42, "source": "attested", "execution_id": "run-981",
           "score": 65.0,
           "provenance": {"schema_version": "2.0", "definition_hash": "<64 hex, revision 2>",
                          "reference": "7", "revision": 2}},
  "score_delta": null,
  "improved": null,
  "explanation": "The outcomes are bound to different definition revisions, so the overall score is not comparable as a whole and score_delta is null. ...",
  "changed_definition_sections": ["criteria"],
  "criteria": [
    {"criterion_id": "greeting", "status": "reweighted",
     "baseline_label": "Greeting", "head_label": "Welcome",
     "baseline_score": 60.0, "head_score": 80.0, "delta": 20.0,
     "baseline_category": "base", "head_category": "base",
     "baseline_weight": 100.0, "head_weight": 50.0},
    {"criterion_id": "farewell", "status": "introduced",
     "baseline_label": null, "head_label": "Farewell",
     "baseline_score": null, "head_score": 50.0, "delta": null,
     "baseline_category": null, "head_category": "base",
     "baseline_weight": null, "head_weight": 50.0}
  ]
}
```

Had only the label changed, `greeting` would be `improved` with delta 20 (its
weight is unchanged), while the overall `score_delta` would still be `null`
because the definition hash differs. Two submissions bound to the same revision
yield `same_definition` with an overall `score_delta` and `improved` flag.

## Python

```python
from autograder import compare_outcomes, compile_definition, build_pipeline

compiled = compile_definition(definition_json)
pipeline = build_pipeline(definition=compiled)
before = pipeline.run(first_submission).outcome
after = pipeline.run(second_submission).outcome
comparison = compare_outcomes(before, after, compiled.definition, compiled.definition)
comparison.model_dump(mode="json")
```

Outcomes may be models or their JSON; definitions may be `GradingDefinition`,
`CompiledDefinition` or the stored JSON snapshot. The function compiles nothing,
loads no templates and performs no I/O. It raises `ComparisonError` (`code`,
`message`, `side`) for `OUTCOME_NOT_COMPLETED`, `DEFINITION_MISMATCH` (the
definition does not hash to the outcome's provenance, or its criteria/evaluators
differ from the tree), `INVALID_OUTCOME` and `INVALID_DEFINITION`.

See [Terminal outcomes](OUTCOMES.md).
