# Autograder — contributor reference

Read this reference before changing the repository. Integration contracts are
recorded in [docs/contracts/DECISIONS.md](docs/contracts/DECISIONS.md). Reduce
the concepts a developer must understand; remove obsolete paths before adding
abstractions. Breaking contract changes require migration evidence.

## Boundaries

`autograder/` implements grading semantics. `web/` and `github_action/` are hosts:
they collect files, authenticate, select configuration identity, accept work,
persist/publish results and retry delivery. `sandbox_manager/` supplies execution
infrastructure. `execution_host/` composes the concrete providers (`DockerHost`,
`S3FixtureProvider`, the OpenAI provider) into `HostCapabilities`. Core must never
import adapters, infrastructure or provider SDKs, or interpret platform identities,
repository changes, database IDs, or workflow job names. Dependencies point
hosts → `execution_host` → `sandbox_manager` → core;
`tests/unit/test_architecture.py` enforces that direction. The one current
responsibility map is [docs/architecture/overview.md](docs/architecture/overview.md).

Hosts explicitly supply execution, fixture-byte and AI providers through
`HostCapabilities`. Core validates selected files before acquisition, consumes
typed preparation, and closes each owned session before returning its outcome.
See [CAPABILITIES.md](docs/contracts/CAPABILITIES.md).

With the Docker host a session is one sandbox owned by the run from
`SandboxManager.get_sandbox(language, lifetime_seconds=...)` to `dispose(sandbox)`.
Every sandbox stops itself at its lifetime (the run's execution budget, derived
from declared process deadlines, at most `running_timeout`) even if its owner
dies; budgets beyond the host maximum fail before execution with
`EXECUTION_BUDGET_EXCEEDED` (HTTP: 422 at validation/acceptance), and each HTTP
attempt has a derived deadline ([JOBS.md](docs/contracts/JOBS.md#attempt-deadline)). Used sandboxes are
never returned to a pool; disposal forgets a sandbox only after Docker confirms
removal, and a failed removal is quarantined (tracked, counted against capacity,
retried) and surfaces as a cleanup error that never changes the grade. Containers
carry owner leases; startup reclaims only provably dead owners and
`python -m sandbox_manager.reclaim` handles the rest. The control API is private,
bearer-authenticated and single-worker ([SANDBOX.md](docs/contracts/SANDBOX.md)). Fixtures are an uncached host
`reference -> bytes` call; `FixtureNotFound` is a non-retryable
`PREPARATION_ERROR`, other provider failures are retryable.

## Public Python and JSON contracts

```python
from autograder import compile_definition, build_pipeline
compiled = compile_definition(definition_json)
pipeline = build_pipeline(definition=compiled)
execution = pipeline.run(submission)
terminal_json = execution.outcome.model_dump(mode="json")
```

`GradingDefinition` v1 is one object: `schema_version`, `templates`, `languages`,
`criteria`, optional `preparation`, `feedback`, and `metadata`. Every test has
stable `id`, evaluator `type`, display `name`, object-valued `parameters`, and
relative `weight`. Unknown structural fields and runtime-parameter collisions
are rejected. There are no live list-parameter/name-fallback/test_library paths.

`compile_definition` resolves the registry, validates and normalizes evaluator
parameters, and builds the criteria tree without Docker/network/provider calls.
The normalized values are the ones executed. Built-in evaluator discovery exposes
JSON Schema derived from these same contracts. Trusted Python templates can be
supplied with `templates={identifier: TemplateInstance}`; uploaded code is not
supported. Preserve injected templates when passing a compiled definition.

Normalization happens once, on raw authoring input. Stored/attested snapshots are
reloaded with `compile_snapshot` (validated, never re-normalized). A
`CompiledDefinition` is created only by those functions and is deeply immutable;
evaluators and reports receive isolated copies of the frozen parameters.

See [DEFINITIONS.md](docs/contracts/DEFINITIONS.md) and the checked-in v1 JSON
Schemas and valid/invalid examples. The offline converter is an explicit migration
tool, never a fallback inside the public parser.

## Submission and execution

`Submission` contains files (`SubmissionFile` filename/content), opaque submitter
and assignment identifiers, optional language, locale, and optional evaluation
scope. Adapters decide which files to collect. Domain-specific file context goes
in metadata; core owns only typed values it must actually interpret.

Language is inferred for a single-language definition. Multiple allowed languages
require explicit selection. Disallowed language and unavailable execution
capability are different failures. Runtime context cannot be assignment-authored.
`autograder/models/language.py` is the only language list; hosts map languages to
images (`sandbox_config.yml` `runtimes:`), I/O evaluators choose commands and
analysis chooses grammars per file type. See
[LANGUAGES.md](docs/contracts/LANGUAGES.md).

The recursive tree retains base/bonus/penalty, nested subjects, tests and the
explicit mixed-group `subjects_weight` split. Sibling weights are ratios; all-zero
siblings share equal weight. Base weight is 100. Bonus adds `score/100 * cap`;
penalty subtracts `(100-score)/100 * cap`; final score clamps to 0–100.

`TestNode` embeds an evaluator implementation, normalized parameters, file target,
weight and criterion ID. Display names may repeat or contain slashes: they never
identify AI batch outputs, result leaves, score vectors, or comparison deltas.
The assessed result is the frozen `ResultOutcomeTree` built once by
`grade(criteria, results)`; leaves own their data and never reference compiled
nodes. Traversal, effective weights and score arithmetic live only in
`models/contracts/scoring.py`; `verify_outcome_tree` checks local and attested
trees against the definition alike.

The runtime order lives in `AutograderPipeline.run` as explicit calls:

```
validate submission → acquire/prepare session? → assess (one AI batch)
                    → grade → requested focus/feedback? → close → outcome
```

Compilation supplies the templates and criteria tree directly. Intermediate
values are local arguments and return values, never stored in diagnostic events.
The optional observer receives frozen observations with no grading data.
Observer failures cannot alter the grade or execution order.

Optional resources depend on selected tests/preparation, not merely other
unused evaluators in a template. Batch AI results must exactly cover criterion
IDs. There is no provider retry fallback or silent zero for missing assessments.
`assess_criteria` runs ordinary evaluators and gives all selected AI criteria to
`assess_many` (one `AssessmentProvider.assess` call, ID-keyed, shared validation for
any group size); the grader only aggregates the merged ID-keyed results.

Feedback is requested: only `feedback.enabled` calls `render_feedback(tree,
preferences, locale)` (focus + the one `default` Markdown report, reading the
canonical preferences); disabled feedback does no work and stays `disabled`.

Required failures produce null score/tree. Submission-category failures
(missing file, failed setup step, language) explain themselves in the
submission's locale, with a bounded setup-output excerpt unless the step is
`private_output`; other categories keep fixed messages. A student program's nonzero exit or
timeout during evaluator assessment produces a valid zero; compilation belongs in
setup commands (`PREPARATION_FAILED`), and a runtime command that cannot start is
not a zero (`PROCESS_START_FAILED`). Who ended a sandbox comes from host-side
evidence: host stop/removal is `SANDBOX_ERROR`, student exhaustion
(`SandboxExhausted`) is an assessed zero. Every process runs
through `ExecutionSession.run_process(ProcessRequest)`: explicit argv or explicit
shell, exact stdin bytes, a deadline that kills the process tree, and
classification by exit status only. Infrastructure failures are exceptions, not
results. See [PROCESSES.md](docs/contracts/PROCESSES.md). Preparation
failures stop before assessment. Optional focus/feedback/comparison failures
preserve the completed grade with a separate enrichment status.

`evaluate_submission` returns the immutable versioned terminal artifact;
`build_pipeline(...).run(...).outcome` retains a frozen return envelope.
There is no mutable execution journal, artifact accessor or result reconstruction.
Cleanup runs on every owned-session path before finalization. Cleanup errors
reach host logging and the optional observer while preserving the grading outcome.
See [OUTCOMES.md](docs/contracts/OUTCOMES.md) for the failure matrix and invariants.

## Adding an evaluator

The recipe is [docs/architecture/extending.md](docs/architecture/extending.md);
`examples/contracts/custom_evaluator.py` (static) and
`examples/contracts/execution_evaluator.py` (fake execution session, no Docker)
are its runnable examples, executed by `tests/unit/test_architecture.py`.

1. Implement `TestFunction` with `execute(self, evaluation, *, <parameters>)`
   (`AiTestFunction`: `build_prompt` with the same shape). `evaluation` is the typed
   `EvaluationInput` (`files`, `language`, `locale`, `session`); keyword-only
   parameters are the normalized configuration. No `*args`/`**kwargs`.
   An evaluator declaring `sandbox_execution` also declares `process_timeouts`
   (the deadline of each process one assessment may run; `BaseExecutionTest`
   declares its one run).
2. The annotated keyword-only parameters are the contract (or supply an explicit
   `config_schema` with the same fields). Declare constraints and descriptions with
   `Annotated[..., Field(...)]`; primitive types imply none. Put cross-field or
   language-dependent semantics in the pure `validate_parameters` hook.
3. Add the instance to a trusted `Template(name, description, evaluators)`; it is
   registered under its own `name`. Invalid signatures fail at registration.
   Capabilities are declared only on evaluators, never on templates.
4. Reference the evaluator `name` as criterion `type`, with a distinct instance `id`.

Evaluators are shared and must be stateless; keep per-submission state in the call.
Only evaluators declaring `sandbox_execution`/`http_network` receive a session;
they run processes only through `session.run_process(ProcessRequest...)` or the
public `BaseExecutionTest` helpers. Authors import only from `autograder`.

Do not add adapter vocabulary or a new pipeline framework for one evaluator.
Provider/system failure raises `EvaluationError` with a published code (OUTCOMES.md) and a fixed safe public message;
ordinary assessment returns a finite `TestResult` in 0–100.

## Adapter contracts and publication

HTTP config resources have canonical IDs, assignment aliases, semantic revisions
and conditional PATCH. Each accepted execution binds a definition snapshot/hash
and revision. Activation gates new acceptance, not already bound jobs. Legacy
history is explicitly unverified, never attributed to today's definition.

HTTP polling is compact, authenticated details contain the full artifact/files,
and history is bounded and deterministically ordered. External results are
validated authenticated host attestations with the exact snapshot and provenance;
they are not proof that this server executed the grader.

Every non-public HTTP route requires a bearer token: the integration principal,
or a per-producer attestation principal limited to publishing external results
([AUTH.md](docs/contracts/AUTH.md)). Accepted submissions are durable PostgreSQL
jobs claimed by leased, UUID-fenced workers ([JOBS.md](docs/contracts/JOBS.md)).
An `Idempotency-Key` makes acceptance and attestation replay-safe per principal
([REPLAY.md](docs/contracts/REPLAY.md)). The Action keeps submitter, actor and
producer identities separate and refuses untrusted events and runners
([trust.md](docs/github_action/trust.md)). Baseline comparison is the pure
`compare_outcomes` over two stored completed outcomes and their bound
definitions, joined by criterion ID; it is read-only and never a grading stage.

The engine finalizes/cleans up before adapter publication. No exporter step, sink
interface, Upstash, Classroom check mutation, or automatic feedback commit remains.
Actions saves a canonical artifact before explicit optional cloud publication;
HTTP saves a private publication receipt before database delivery. Delivery retry
reuses the finalized outcome without grading again. Never report a completed
grade as failed because a sink failed.

## Current behavior and plans

This file describes implemented behavior. Not implemented (do not document or
rely on them as current): a host supplying `server_execution` (API-testing
criteria fail with `SERVER_CAPABILITY_UNAVAILABLE` on the shipped hosts), job
scheduling beyond submission-order claiming (priority, fairness, quotas), a shared
or distributed sandbox handle store, feedback modes other than `default`, and
fixture caching. Refactor progress is tracked in GitHub issue #363.

## Verification

Run meaningful tests for changed behavior. Contract tests cover compile purity,
actual execution of normalized values, invalid paths, outcome invariants, snapshots,
optimistic concurrency, migrations, adapter wire parity and publication retry.
Docker integration tests exercise real grading isolation. Architecture tests
(`tests/unit/test_architecture.py`) protect dependency direction, catalog/example
truthfulness and the extension path. `make verify` is the hermetic path (lint,
schema drift, strict docs build, unit and SQLite HTTP tests); `make test-postgres`,
`make test-integration` and `make test-e2e` are the database and Docker tiers. CI
runs exactly these targets and deploys only after all pass; see
[the development guide](docs/guides/development.md#verification). Preserve unrelated work;
use a clean worktree for delivery. Do not add co-author commit trailers.
