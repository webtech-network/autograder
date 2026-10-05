# Integration contract boundaries

Grading semantics belong to the engine. Transport, persistence, credentials,
acceptance, publication, and submission identity belong to hosting adapters.
The version 1 wire contract has one parser and one terminal outcome format.

## Definition

`schema_version: "1.0"`, `templates: [identifier]`, `languages: [language]`,
`criteria`, optional `preparation`, `feedback`, and optional `metadata` constitute
one definition. Structural unknown fields are errors. Criteria retain base,
bonus, penalty, nested subjects, relative sibling weights, and the explicit
`subjects_weight` split. Tests require `id`, `type`, `name`, and object-valued
`parameters`; IDs are globally unique within a definition. Display names are
never identities. Base weight is 100; bonus and penalty weights are caps.

Preparation has language-keyed required files and named setup commands, and
fixtures identified by logical reference and a relative fixture-root path. Required-file paths are relative to the submission root.
The current Docker host mounts fixtures under `/tmp/app/`; commands reading
fixtures use that documented root. Provider credentials remain host-owned.
Feedback has `enabled`, `mode: "default"`, and typed preferences. Only the
implemented feedback mode is accepted. Language IDs are the
canonical lowercase enum; a single allowed language is inferred, while multiple
languages require an explicit selection at submission time. Missing host
capabilities are execution failures, distinct from disallowed languages.

`compile_definition` is pure: registry lookup, evaluator parameter validation,
normalization, command coverage, and tree compilation perform no Docker,
network, provider, or persistence work. The compiled normalized parameter values
are the values executed. Public errors carry machine codes and JSON paths.
Definition hashes are SHA-256 over sorted, compact UTF-8 normalized JSON.

HTTP create/update stores only compiled normalized definitions. Config identity
is the canonical resource ID; external assignment ID is an alias. PATCH requires
an optimistic revision precondition, preserves omitted fields, and rejects nulls.
An execution retains an immutable normalized definition snapshot, its hash, and
revision. Activation gates new submissions, not already bound executions.
Old records without snapshots are explicitly unverified; current definitions
must never be used to fabricate historical provenance.

## Terminal outcome and failure policy

A terminal outcome has `schema_version: "1.0"`, discriminated `status`,
`execution_id`, `language`, provenance (`schema_version`, `definition_hash`,
optional opaque `reference` and positive `revision`), UTC start/finish timestamps,
nonnegative `duration_ms`, `score`, `tree`, `feedback`, and `error`.

* `completed`: finite score 0–100, one authoritative typed result tree, no
  top-level error. A genuine failed student criterion may yield zero.
* `failed`: null score and tree, a required safe structured error. No partial
  tree can masquerade as a valid grade.
* Evaluator compilation errors, student runtime errors, and student execution
  timeouts are assessed criterion results. Required-file/preparation failures
  stop before assessment and fail without a grade.
* Sandbox transport/system failures, AI/provider failures, invalid scores, and
  absent/duplicate required evaluator outputs fail without a grade.
* Optional focus/feedback/comparison enrichment failure preserves a completed
  grade and is represented by its own disabled/completed/failed status.

Safe errors expose code, fixed safe message, category, retryability, and an
execution correlation ID, never raw exceptions, provider responses or step
class names. Diagnostics are internal. Criterion IDs identify tree leaves and
AI batch outputs, including repeated evaluators and duplicate display labels.

External ingestion is an authenticated host attestation, not proof that this
server ran the grader. It validates the definition snapshot/hash, language,
revision, result IDs/types, and outcome invariants. It may attest older or
inactive known revisions. Compact polling excludes files/tree; explicit details
and bounded deterministic history projections expose the same stored outcome.

## Finalization and publication

The engine cleans up resources and returns a finalized terminal outcome before
any adapter publication. No exporter is a grading step. Delivery failure cannot
change a completed grade into a failed execution or trigger a contradictory
second upload. Actions writes the canonical artifact before optional cloud
publication, reports delivery failure separately, and permits explicit artifact
retry without regrading. Actions uses ordinary summary, scalar outputs, and local
artifacts, independently of workflow job name and repository write permissions.

## Migration and limits

An explicit offline converter handles the old multi-file/list-parameter format.
Ambiguous parameters, unsupported fields and invalid definitions are rejected
with paths; stored invalid definitions are quarantined inactive rather than
silently accepted. The HTTP migration records snapshots only for future
executions and labels unsnapshotted history unverified. Workflow instructions
cover the single-definition-file and scalar output changes.

The definition and outcome schemas do not provide durable scheduling,
distributed sandbox provisioning, submission idempotency, or retention policy.
Those are hosting responsibilities.

## Discovery and trusted Python extensions

The typed template/evaluator catalog derives parameter schemas and validated
samples from the same contracts used by compilation. Capability requirements
and known language constraints live on evaluator implementations. Discovery does
not probe host availability. `compile_definition`, `describe_templates` and
`evaluate_submission` form the supported facade; evaluation returns the finalized
terminal outcome. Trusted instantiated `Template` objects may be injected by
identifier and retained through recompilation. JSON transports accept built-in
identifiers only. No uploaded code or dynamic plugin loader is supported.

The current facade uses existing host configuration. Host-supplied resource
interfaces and ownership remain INT-14 work. See [CATALOG.md](CATALOG.md) for the
INT-11 implementation contract, deployment assumptions, migration and issue
coordination; internal pipeline classes are not a compatibility promise.

## Deliberate execution

The web adapter provides a bounded synchronous `POST /api/v1/execute` for
pre-submission runs. It uses `test_cases` as stdin lines and `results` as an
ordered list, separate from grading-tree orchestration.
Authentication uses the existing host integration token. The shared sandbox
manager's per-language pool is the current common admission limit for grading
and deliberate runs. A process failure is a 200 result with stdout, stderr,
exit status and category; an infrastructure failure is 503, and a connected
caller past the response deadline gets 504. A cancelled/timed-out HTTP request
does not cancel its single worker; the worker owns cleanup. See the
[execution contract](../features/deliberate_code_execution.md) for limits and
the error matrix. The response deadline does not impose a hard deadline on
blocked Docker or asset-provider calls.
