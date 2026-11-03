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
identifier and retained by the immutable compiled definition. JSON transports accept built-in
identifiers only. No uploaded code or dynamic plugin loader is supported.

The facade accepts explicit host capabilities. Providers are borrowed; returned
execution sessions belong to one run and close before finalization. Selected
language, selected evaluator instances and selected preparation drive one
requirements decision. See [CAPABILITIES.md](CAPABILITIES.md). See [CATALOG.md](CATALOG.md) for the
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

## Assessment inputs

[File selection](FILES.md) is shared by ordinary and AI assessment. Structural
parsing belongs to the static evaluator and happens within its own assessment;
there is no pipeline-wide structural-analysis stage or grader-level AST cache. Explicit targets
and required file counts fail clearly rather than silently omitting criteria.

## Submission inputs and evaluator files

HTTP and Actions share bounded canonical UTF-8 input validation outside the core.
Accepted source is preserved exactly; no implicit path, encoding or newline
normalization is performed. File metadata and changed-line absence survive
authenticated details. Scope is a validated subset of source names, not a privacy
boundary. See [SUBMISSIONS.md](SUBMISSIONS.md) for limits and client migration and
[FILES.md](FILES.md) for assessment targets versus execution/context files.

## Explicit orchestration (ARC-01)

Compilation supplies the tree and trusted evaluators. Runtime uses direct calls
with local intermediate values; no diagnostic journal is used as artifact storage.
The step registry, wrappers and artifact accessors are removed. Required failure
and optional feedback handling have separate explicit boundaries. Session cleanup
precedes terminal outcome construction; cleanup errors reach host logging and an
optional observer without replacing the grade. Disabled feedback calls neither
focus nor reporting. The supported facades and v1 wire schemas are unchanged.
See [Python migration and execution order](../core/pipeline-architecture.md).

## Immutable compiled definitions (ARC-02)

Raw authoring input is normalized exactly once by `compile_definition`. The same
canonical values form the snapshot, its hash, the executed parameters and the
parameters reported in the outcome; tree construction never re-applies evaluator
normalizers. Stored or attested snapshots (HTTP configurations, bound execution
snapshots, external results, Action cloud configurations) are loaded with
`compile_snapshot`, which validates structure, registry, contracts and cross-field
rules but keeps parameter values verbatim and requires every contract field to be
explicit. A `CompiledDefinition` is created only by these two functions and is
deeply immutable: `definition` returns a fresh copy, tree nodes are frozen, and
parameters are frozen JSON values. Each evaluator invocation and each reported
result receives an isolated mutable copy, so executions from one plan cannot
affect one another. v1 JSON shape and hash rules are unchanged.

## Evaluator-owned contracts (ARC-03)

An evaluator is a local change: its implementation, its parameter contract and
its registration. The supported invocation shape is

```python
def execute(self, evaluation: EvaluationInput, *, <normalized configuration>) -> TestResult
```

(`build_prompt` with the same shape for AI evaluators). `EvaluationInput` is a
small frozen value with `files` (the selected assessment files, carrying their
metadata and changed lines), `language`, `locale` and `session`. The session is
bound only to evaluators declaring `sandbox_execution` or `http_network`; AI
results reach no evaluator, because the grader takes each AI criterion's result
from the provider batch. Keyword-only parameters are exactly the contract fields
and receive an isolated copy of the canonical values. Template registration and
compilation reject any other signature (`*args`, `**kwargs`, extra positional
parameters, unannotated configuration, fields that disagree with an explicit
`config_schema`, or runtime names used as configuration) with `INVALID_TEMPLATE`.

Constraints come only from the evaluator: annotations and defaults are used
verbatim, with bounds declared through `Annotated[..., Field(...)]` or an explicit
Pydantic model. Field descriptions document the catalog; there is no separate
parameter-description list. Semantics that a JSON contract cannot express (built-in
command coverage, keyword support and ast-grep rule compilation for every allowed
language) live in the evaluator's pure `validate_parameters(parameters, *,
languages)` hook, which returns `ParameterIssue(code, path, message)` values. The
generic compiler interprets no parameter names, so unrelated evaluators may reuse
names. Registry lookup is implemented once by `Template`.

Evaluator instances are shared by every submission and thread that uses their
template and must be stateless. Per-submission state lives in the call
(`EvaluationInput`, parameters, locals) or in the grader that owns one traversal.

## Sandbox ownership and private control API (ARC-09 / INT-15)

One `DockerSession` lease owns a sandbox from acquisition through disposal. It
borrows a host-owned manager. Local and remote managers share `acquire`/`dispose`.
Every disposal destroys the container, and repeated disposal is defined. The
competing release/destroy APIs, the module-global manager and library signal
handlers are removed. A pool forgets a container only after Docker confirms
removal. Failed removals are retained, retried and reported, and they still hold
capacity. Startup reclaims only owners proven dead by an acquirable lease lock,
so a second live host never removes the first host's containers. One
`SandboxRuntimeProfile` owns Docker options, and the runtime is the only
difference between runsc and runc.

The control API is private, token-authenticated and single-worker. Each lease is
bound to a client-generated secret. Unknown/expired handles, missing artifacts
and execution failures have distinct responses that the client preserves.
Acquisition and disposal are safely replayable; commands are never replayed. A
distributed handle store is unnecessary for the documented single-process
deployment. See [SANDBOX.md](SANDBOX.md) for the boundary, limits, recovery
table and migration.
