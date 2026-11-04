# Core values

The values that pass between the core's operations, as implemented. Wire
schemas are defined by the [contracts](../contracts/DECISIONS.md) and their
checked-in JSON Schemas; this page explains how the Python values relate and
does not repeat those schemas. Ownership of each module is in the
[responsibility map](overview.md).

## Definition, compiled definition and criteria tree

A `GradingDefinition` v1 ([DEFINITIONS.md](../contracts/DEFINITIONS.md)) is
authored JSON. `compile_definition` resolves trusted templates, normalizes every
criterion's parameters once with its evaluator's contract and returns a deeply
immutable `CompiledDefinition` (normalized definition, hash, templates and the
executable `CriteriaTree`). Stored snapshots are reloaded with
`compile_snapshot`, which validates without re-normalizing.

```text
CriteriaTree
├── base     (weight 100)          subjects and/or tests
├── bonus    (optional cap 0–100)  subjects and/or tests
└── penalty  (optional cap 0–100)  subjects and/or tests
```

- Every category may contain nested subjects, tests or both; a mixed group
  splits its weight with an explicit `subjects_weight`.
- Weights are nonnegative. Sibling weights are ratios, and all-zero siblings
  share equally. Bonus and penalty weights are caps, never negative numbers.
- The final score is `base + bonus/100 * bonus_cap - (100 - penalty)/100 *
  penalty_cap`, clamped to 0–100. The arithmetic exists once, in
  `models/contracts/scoring.py`.
- A `TestNode` holds the criterion ID, evaluator, normalized parameters, file
  target and weight. Display names may repeat or contain slashes; criterion IDs
  identify results, score vectors and comparison deltas.

## Evaluator result and assessed tree

An evaluator returns a frozen `TestResult(test_name, score, report)`.
Assessment returns one result per criterion ID, and `grade(criteria, results)`
builds the frozen `ResultOutcomeTree` once. Its leaves (`TestOutcome`) own their
criterion ID, evaluator ID, label, file target, canonical parameters, effective
weight, score and report as data. There is no `root` wrapper and no second,
mutable result tree. `verify_outcome_tree` checks local and externally attested
trees against the definition in the same way.

## Terminal outcome

`evaluate_submission` returns the immutable [outcome v1](../contracts/OUTCOMES.md):
execution identity, provenance, language, timestamps, score and tree (null on a
required failure), feedback status and a safe error. A completed zero is
distinct from a failed run. `build_pipeline(...).run(...)` returns a frozen
envelope whose only field is that `outcome`. Optional
[diagnostic events](pipeline_execution_tracking.md) carry no grading data and
are not an API output.

## Submission

`Submission` holds opaque submitter and assignment identifiers, files
(`SubmissionFile(filename, content, changed_lines=None, metadata=None)`), an
optional language, locale and optional `EvaluationScope(scoped_files)`. See
[SUBMISSIONS.md](../contracts/SUBMISSIONS.md) and [FILES.md](../contracts/FILES.md).

| Field | Core behavior | Intended use |
|-------|---------------|--------------|
| `EvaluationScope.scoped_files` | Shapes file selection | Files that are the primary subject of evaluation |
| `SubmissionFile.changed_lines` | Available to evaluators; used by structural analysis | Added or modified lines |
| `SubmissionFile.metadata` | Never interpreted; kept on the selected files | Opaque per-file context |
| API `metadata` / database `submission_metadata` | Never read by the core | Submission-level provenance and audit context |

Platform- or domain-specific data belongs in metadata, not in new typed core
fields. Evaluators receive the selected original files as `evaluation.files`.

## Templates and evaluators

A `Template` is a trusted registry `{identifier: TestFunction}`; lookup is
implemented once by the base class. A `TestFunction` declares its parameter
contract through the keyword-only parameters of `execute(evaluation, *, ...)`,
and may add `validate_parameters` and file rules. `EvaluationInput` holds
`files`, `language`, `locale` and `session` (only for evaluators declaring
`sandbox_execution` or `http_network`). The recipe and runnable examples are in
[Adding an evaluator](extending.md).
