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
Those are hosting responsibilities; the HTTP host provides replay-safe operation
keys ([REPLAY.md](REPLAY.md)).

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
Authentication uses the host integration token (see [AUTH.md](AUTH.md)). The shared sandbox
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

## HTTP trust boundary (INT-01)

The web API is a trusted application-to-application boundary. Authentication is
declared once per router: health, readiness and the static template catalog are
public; external-result attestation needs the `attest` scope; every other route,
including all configuration aliases, submission reads and deliberate execution,
needs the `integration` scope. All integration principals share all resources;
caller-supplied user identifiers never authorize. Restricted attestation tokens
let a producer publish without reading data. A missing credential configuration
fails closed (503) and readiness reports it. See [AUTH.md](AUTH.md).

## Replay-safe acceptance and publication (INT-04)

`Idempotency-Key` on acceptance and attestation is scoped by authenticated
principal and operation. The key, request fingerprint and created submission ID
commit in the resource's transaction; equal retries (including concurrent ones and
retries after a lost response or a later revision) return the original receipt
without regrading, and a changed request is 409 `IDEMPOTENCY_KEY_REUSED`. Receipts
are retained with their submission. The Action derives its key from the saved
outcome's execution ID, retries only keyed POSTs within a total deadline, honours
`Retry-After`, and reports uncertain delivery without altering the grade. See
[REPLAY.md](REPLAY.md).

## Action identity and runner trust (INT-02)

The Action separates the submitter (explicit opaque `submitter-id`, else the
repository), the actor (provenance only) and the producer (the authenticated
credential). Published metadata records repository, event, event SHA, the evaluated
commit and whether graded files match it, run ID/attempt, workflow ref, actor and
runner. Publication is refused for `pull_request_target`, `workflow_run`, fork pull
requests, unknown events and unreviewed self-hosted runners. Restricted attestation
tokens publish a named revision without reading configurations. Attestations remain
producer claims; untrusted work is graded server-side through a trusted broker. See
[the trust table](../github_action/trust.md).

## Baseline comparison (INT-13)

Consumer: Prisma shows progress between two stored submissions of one
assignment. Owner: the authenticated read-only HTTP operation
`GET /api/v1/submissions/{submission_id}/comparison?baseline_submission_id={id}`,
computed on demand from the two stored canonical outcomes and their bound
definition snapshots; Python consumers use the pure facade function
`compare_outcomes`. No caller-supplied tree, vector or baseline content is
accepted. Comparison is never a grading stage, is never persisted and never
regrades; the outcome's `comparison` enrichment remains `disabled` for normal
grading. Same definition hash permits an overall delta; any other revision
pairing reports per-criterion results by criterion ID (`reweighted` and
`redefined` mark changed meaning) and a null overall delta. Different
configuration resources, incomplete outcomes and unsnapshotted legacy history are
rejected with explained codes. Attested outcomes are compared under the same
rules and labelled `attested`, without claiming local execution. The legacy
`ResultComparator`, its dataclasses, `ResultTree` vector helpers and unused web
comparison schemas are removed; the `score_vector`/`comparison` result columns
are unused legacy storage. See [baseline comparison](../features/baseline_comparison.md).

## Sandbox ownership and private control (INT-15/ARC-09)

One host-owned manager owns a sandbox from acquisition to Docker-confirmed
removal. Release and destroy are one idempotent `dispose` with a defined
status; a used sandbox is never reused. Failed removal quarantines the sandbox:
it stays tracked, counts against capacity, is reported in pool statistics and
is retried a bounded number of times. Timeouts use the same path. Hosts own
signals and call `shutdown()`; the library installs no handlers. Orphan
reclamation is scoped to owner leases (owner id, hostname, boot/pid/start time)
and removes only provably dead local owners; an explicit operator command
handles remote and legacy owners. One Docker profile declares all limits; the
gVisor fallback only drops the runtime argument. The control API is private
(Compose `expose`), requires a bearer token, uses random bounded expiring
handles in one worker process, makes acquisition replay-safe by request id,
tombstones disposed handles, and distinguishes unknown handles from missing
artifacts. See [SANDBOX.md](SANDBOX.md) for the recovery matrix, limits and
migration.

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


## AI batching inside assessment (ARC-07)

Grading is two explicit calls: `assess_criteria(criteria, submission, session=,
ai=)` returns one validated `TestResult` per criterion ID, and
`GraderService.grade_from_tree(criteria, results)` aggregates them. Assessment walks
the compiled tree once (nested subjects before direct tests, the historical
execution order) and prepares every criterion with the shared file-selection
policy. Ordinary evaluators run individually. All selected AI criteria are given
to `assess_many`, which builds their prompts and makes exactly one
`AssessmentProvider.assess(requests, *, context_files, locale)` call; a single
AI criterion is a group of one, so both sizes share validation and error mapping.

Requests are `AssessmentRequest(criterion_id, prompt)` and answers are
`ProviderAssessment(criterion_id, score, report)`; display labels and provider
titles are never identities. Unknown, duplicate, missing and invalid answers, and
non-`EvaluationError` provider exceptions (`PROVIDER_ERROR`), fail the required
grade without retry or zero. There is no AI pipeline stage, no
`assessments`/AI parameter on the grader, no `TestInput`/`test_name` transport and
no result cache on any evaluator. Provider, model, credentials and deadline remain
host capabilities (`HostCapabilities.ai`, #376).

## Self-contained results and one scoring definition (ARC-11)

The assessed result is the terminal `ResultOutcomeTree`, built once per run by
`grade(criteria, results)`. Each `TestOutcome` owns its criterion ID, evaluator
ID, label, file target, canonical parameters, effective weight, score and report
as data; no result references a `TestNode` or evaluator. The duplicate mutable
`ResultTree`/`*ResultNode` model, its `from_dict` reconstruction (which lost data),
`GraderService`/`SubmissionGrader`, `CriteriaTreeProcesser`, the comparison
dataclasses and the unused printers are removed. `TestResult` is a frozen
`(test_name, score, report)` evaluator return value.

`autograder/models/contracts/scoring.py` is the only definition of traversal,
effective weights and score arithmetic, used by grading, outcome validation,
`verify_outcome_tree`, focus and comparison. Definition-versus-outcome structure
is checked by core contract code (`verification.py`) for local and attested
outcomes alike; the HTTP host only supplies the snapshot and translates the error
to 422. Arithmetic stays independently validated by the outcome models.

The previous focus traversal applied a mixed group's `subjects_weight` twice
when ranking feedback; the shared share calculation corrects that ordering.
Tree, scores and v1 wire shape are unchanged (real-container golden in
`tests/integration/test_canonical_outcome_golden.py`).

## Requested feedback (ARC-12)

Feedback is an optional derivation of a completed grade. The coordinator calls
`render_feedback(tree, definition.feedback.preferences, locale)` only when
`feedback.enabled` is true; disabled feedback performs no focus or report work
and stays `disabled` even if those services are unavailable. Any exception or
empty content becomes `failed` with `FEEDBACK_ERROR`, preserving the grade.

Rendering uses the definition's canonical `FeedbackPreferences` directly: there is
no second preference dataclass, no `online_content` rewriting and no stored
locale-dependent defaults, so repeated rendering is pure. The impact-ordering
helper (`find_focus`) and formatter are kept; the reporter factory
(`ReporterService`), the unimplemented AI reporter and its preferences, the
unused `PreflightError` and the unused report translation keys are removed. The
legacy pre-flight feedback generator and pipeline execution serializer were
already deleted with the step framework (#396) and had no remaining callers.
Feedback `mode` stays `"default"` in the v1 schema.
