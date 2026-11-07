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

Safe errors expose code, message, category, retryability, and an
execution correlation ID, never raw exceptions, provider responses or step
class names. Infrastructure, provider and internal messages are fixed;
submission failures are explained to the student (ONB-02, below). Diagnostics are internal. Criterion IDs identify tree leaves and
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

Migrations are the only owner of the HTTP database schema (ENV-02). The API
checks the database revision at startup and refuses to serve any revision but its
own head; it never creates tables. Revisions `001`-`007` are squashed into a
baseline `007`, so empty databases migrate and databases at `007` upgrade
unchanged. See [deployment and migration](JOBS.md#deployment-and-migration).

## Migration notes

What changed for existing definitions, deployments and trusted Python code,
kept here so that the contracts describe only current behaviour.

### Upgrading to 1.0.0

1.0.0 is the first release. The tags before it (`0.0.2`–`0.5.0`, `1.1.2`, `v1`,
`v0.0.0-285-test`) and the deployments built from `main` before the
refactor ([#363](https://github.com/webtech-network/autograder/issues/363)) are
not maintained, and nothing of them is compatible with 1.0.0. The
[changelog](https://github.com/webtech-network/autograder/blob/main/CHANGELOG.md)
lists every change; these are the steps.

**GitHub Action consumers.** Those tags read `criteria.json`, `feedback.json`
and `setup.json` from `.github/autograder/` (or a `template-preset` or
`custom-template` input) and built their image from a Dockerfile in every job.

1. Convert the rubric into one definition, `.github/autograder/definition.json`:
   assemble the old files into the legacy envelope and run the offline
   converter ([Definitions](#definitions)), then check the result and grade a
   reference solution with `python -m execution_host.check`
   ([Test your rubric](../author/testing.md)). Feedback settings move into the
   definition's `feedback`. A repository that followed `main` with a format
   1.0 `definition.json` runs the same converter on it: the result is format
   2.0 with the same criterion IDs, weights and scores.
2. Pin the release: `uses: webtech-network/autograder@1.0.0`.
3. Remove the inputs `template-preset`, `custom-template`, `feedback-type`,
   `include-feedback`, `github-token`, `app-token` and `openai-key` (and
   `redis_url`, `redis_token` and the underscore spellings of `v1`).
   AI criteria read `OPENAI_API_KEY` from the step's `env`. The job needs only
   `contents: read`: nothing commits feedback or updates Classroom checks.
4. Read the `status`, `score` and `result-path` outputs instead of `result`
   (base64) and `total_score`, and upload `.autograder/` with
   `actions/upload-artifact` to keep the outcome
   ([Inputs and outputs](../github_action/configuration.md)).
5. With the cloud, keep `execution-mode: external` and `grading-config-id`,
   and add `upload-to-cloud: "true"` where results must be published; the
   server must run 1.0.0 too. Its identity rules are in
   [Identity and trust](../github_action/trust.md).

Definitions that run code need Docker on the runner; every Linux GitHub-hosted
runner has it ([Requirements](../github_action/README.md#requirements)).

**HTTP integrators.**

1. Send `Authorization: Bearer <integration token>` on every route except
   health, readiness and the template catalog
   ([HTTP authentication](#http-authentication-int-01)).
2. Create configurations with one format 2.0 definition (validate first with
   `POST /api/v1/configs/validate`) and update them with conditional `PATCH`
   ([REST API](../API.md)).
3. Treat `POST /api/v1/submissions` as acceptance (`202` and `Location`), poll
   the compact status, read files and trees from the authenticated details
   ([Submission details](#submission-details)), and send an `Idempotency-Key` so
   that retries are safe ([Replay safety](REPLAY.md)).
4. Read results as the terminal outcome: `failed` has a null score and a coded
   error ([Terminal outcomes](#terminal-outcomes), [Outcomes](OUTCOMES.md));
   do not resubmit on `retryable: true` ([Execution retry](#execution-retry-cor-03)).
   Send `locale` as `en` or `pt-br`.
5. Read the catalog's `evaluators[].identifier` and `required_capabilities`
   ([Catalog](#catalog-int-11-onb-08)).
6. Send and store format 2.0 definitions, and re-read stored configurations
   after the upgrade: the server converts them into a new revision, so a stale
   `If-Match` gets `412`. Accept `provenance.schema_version` `"1.0"` (history)
   or `"2.0"`, read `definition_snapshot` in the format that provenance names,
   and attest only 2.0 snapshots ([Definitions](#definitions)).

**Operators of the HTTP service.**

1. Back up the database and drain the old API, then bring the schema under
   migrations ([Existing databases](JOBS.md#existing-databases)). The
   migrations convert stored definitions to format 2.0 and log the
   configurations they quarantine; PATCH a corrected definition and reactivate
   each one ([Definitions](#definitions)).
2. Remove the [retired variables](../operate/configuration.md#retired-variables),
   set `AUTOGRADER_INTEGRATION_TOKEN` and `SANDBOX_API_TOKEN`, and write
   `sandbox_config.yml` from the shipped one: `general.runtime`,
   `general.max_sandboxes`, `running_timeout` and the `runtimes:` map
   ([Sandbox ownership and configuration](#sandbox-ownership-and-configuration)).
   With `runtime: runsc`, Docker must list gVisor.
3. Deploy the `1.0.0` images of `autograder-api` and
   `autograder-sandbox-manager` and the runtime images `sandbox_config.yml`
   pins, following the [upgrade runbook](../operate/deployment.md#upgrade-runbook)
   (`python -m web.main --check`, then the migrations).
4. Remove containers of the old sandbox managers:
   `python -m sandbox_manager.reclaim --legacy`.

### Definitions

Convert one legacy definition envelope offline:

```sh
python -m autograder.services.definition_migration old-definition.json definition.json
```

Supply `template_name`, `grading_criteria`, `languages` and optional legacy
setup/feedback fields. Multi-file repository configurations must first be
assembled into that envelope. The converter assigns deterministic path-based IDs
once, preserves weights/labels, moves the known `display_name` parameter to the
label, removes the runtime language placeholder and converts the old file-target `all`
  sentinel to null, and resolves only unambiguous
learning-resource labels. Persist these new IDs; do not regenerate them on edits.
Duplicate pairs, competing encodings, unsupported options and unsafe asset
relocation require explicit instructor correction. There is no runtime converter.

Migration 005 converts database rows, records rejection evidence, quarantines
invalid rows inactive, and drops old configuration columns. Future submissions
retain exact snapshots/hash/revision. Old submissions remain `unverified_legacy`;
old failed numeric zeros become null grades. The migration is intentionally
irreversible: back up first, drain old background executions, deploy the matching
engine/API/Action consumers together, run Alembic upgrade, inspect quarantined rows,
then reactivate only corrected definitions. Rollback restores the pre-upgrade DB
backup with the previous code. Automatic schema creation does not migrate a DB.

The old `test_library` envelope is unsupported. Multiple templates use an
explicit list with collision-checked registry resolution. Evaluator parameters
have typed contracts and stable criterion IDs. Provider mapping, resource limits,
and infrastructure scheduling belong to the hosting environment rather than
the definition schema.

#### Definitions that compile no longer (ONB-01)
Definitions that compiled before may now be rejected, intentionally: an explicit
presence threshold of `0`, an empty forbid/find list, or a standalone shell
operator in a command. Nothing else changes: a stored snapshot lists every
parameter explicitly, so a valid snapshot keeps its meaning and hash, and a
raw definition that omitted a threshold now gets 1 instead of an always-passing 0.
There is no runtime fallback. A stored configuration that became invalid is
rejected with the exact path (`422` on submission, a failed outcome for a job
already bound to it) until it is corrected; nothing rewrites it silently.

Before deploying, check every stored definition with the offline converter,
which compiles v1 input unchanged and prints the precise errors:

```sh
python -m autograder.services.definition_migration stored.json checked.json
```

Then correct each rejected definition through the configuration API (`PATCH`
creates a new revision): set the intended threshold, name the forbidden items or
delete the criterion, and move compile steps such as `javac A.java && java A`
into `setup_commands` (`javac A.java`) with `program_command: "java A"`. A
legacy envelope carrying these values is rejected by the converter in the same
way, so migration 005 would quarantine such a row.

### Host capabilities

* **One fixture-set call (PRF-03).** `ExecutionSession.stage_fixture(path,
  content, read_only)`, called once per fixture, is replaced by
  `stage_fixtures(fixtures: Sequence[StagedFixture])`, called once with the
  whole set (`StagedFixture` is in `autograder.models.execution`). A host
  session that implemented `stage_fixture` renames it and loops over the
  sequence, or better stages the set in one operation. No definition, wire or
  configuration change. Fixtures are now all fetched before any is staged, so a
  missing fixture leaves nothing staged; the outcome is unchanged
  (`capability / PREPARATION_ERROR`). With the Docker host a grading's fixture
  set went from one `docker exec` per fixture (100 for the 100-fixture maximum,
  about 3 to 4 s) to one.

#### Earlier architecture issues

The simpler sequence resolves the intent of #302 and #307–#312 through selected
requirements, pure validation, explicit providers, typed preparation and one
owner for cleanup. It does not introduce step categories, setup inheritance,
provider retry, or publication inside the engine. Language-keyed preparation
already expresses the required variation; a new pipeline framework is unnecessary.

| Earlier proposal | Resolution in the current contract |
| --- | --- |
| #302 decompose preflight | Keep the short preparation sequence; resource acquisition and pure validation are separate. |
| #307 add step categories | Superseded: no runtime behavior needs category labels. |
| #308 add FileCheckStep | Fulfilled by pure bootstrap validation before any provider call; a separate step class is unnecessary. |
| #309 add AssetInjectionStep | Fulfilled by typed fixture staging through the acquired session. |
| #310 add SetupCommandsStep | Fulfilled by typed selected-language commands after fixtures. |
| #311 merge template setup | Superseded: evaluator capabilities and explicit definition preparation express current requirements without inheritance. |
| #312 remove PreFlightStep | Completed by ARC-01: typed preparation is a direct function call; the wrapper, legacy parsing and provider construction are removed. |

### Processes (ARC-08, COR-01)

| Before | Now |
| --- | --- |
| `run_command(cmd)` split with `shlex`, but malformed quoting silently ran `/bin/sh -c cmd` | `ProcessRequest.command(cmd)` raises. Compilation rejects such definitions (`INVALID_COMMAND`). |
| `run_commands(inputs, program_command=...)` ran `echo '<joined>' \| cmd` | Exact stdin: `lines_to_stdin(inputs)` |
| `inputs: []` sent one newline (`echo ''`) | Empty stdin (EOF). Use `[""]` to send one empty line. |
| An input `-n` (or `-e`, `-E`) could be taken as an `echo` option and lost | Sent literally, as `-n\n` |
| Exit ≠ 0 with unrecognised stderr was `SYSTEM_ERROR` → `SANDBOX_ERROR`, a failed grade | Assessed zero (`runtime_error`) |
| Exit 137 was `TIMEOUT` | `runtime_error` with exit code 137 |
| A container stopped under a process kept the process's exit code (`_stopped_result`): a reaper or `docker kill` turned a correct run into a zero | Host-ended containers raise `ProcessExecutionError` (`SANDBOX_ERROR`); only host evidence of exhaustion is the submission's (`SandboxExhausted`) |
| PID 1 and the collector ran as `sandbox`: a submission could kill them and turn a bad grade into a retryable `SANDBOX_ERROR` | PID 1 and control execs run as `root`; the submission cannot signal them |
| A missing or non-executable `./a.out` was `PROCESS_START_FAILED` | Assessed zero (only a runtime command that cannot start is a capability failure) |
| An artifact the submission made unreadable was `ARTIFACT_READ_FAILED` → `SANDBOX_ERROR` | Read and graded |
| `compilation_error` from stderr keywords (`error:`, `gcc`, ...) | `runtime_error`. Compile in `setup_commands` to get `PREPARATION_FAILED`. |
| Unbounded `exec_run` output buffering | Bounded per stream at the host |
| A timeout stopped waiting but left the process running | The process and its children are killed before the call returns |
| Control API `POST /run`, `POST /run-batch` | `POST /process` |

Definitions that depended on the old behaviour need these changes:

* An `expect_output` test with `inputs: []` whose program calls `input()` now
  gets EOF. Add `[""]` if the program must read an empty line.
* A `program_command` or setup command that relied on shell syntax never ran
  through a shell before (it was split into arguments) unless its quoting was
  malformed. Write `sh -c '...'` explicitly. Malformed quoting and standalone
  shell operators are now rejected when the definition is compiled or loaded.
* Assignments that expected `compilation_error` from an I/O run should compile
  in `preparation.languages.<language>.setup_commands`.

### Per-test sandbox cost (PRF-08)

The runner forked `mkdir` and `base64` to write stdin (sent as base64) and the
collector forked fourteen helpers,
returning outputs as base64. The runner now forks none (text stdin up to 48 KiB
is one argument) and the collector five, returning raw bytes; see
[Cost of a process](PROCESSES.md#cost-of-a-process). Medians of `run_process`
for a program that upper-cases one line, on the same machine and profile,
before and after:

| Runtime | Python | Java | C |
| --- | --- | --- | --- |
| gVisor | 195 → 122 ms | 290 → 164 ms | 100 → 67 ms |
| runc | 106 → 103 ms | 118 → 110 ms | 95 → 83 ms |

A test's marginal cost in complete python-io gradings fell from 216 to 126 ms
under gVisor (a 21-test grading from 5.0 to 2.8 s) and from 160 to 154 ms
under runc. Nothing changes for definitions or deployments.

### Sandbox ownership and configuration

* **Explicit runtime and read-only root (COR-04).** `general.runtime` is
  required in `sandbox_config.yml` (`runsc` or `runc`); a configuration without
  it is rejected at startup with a message naming the choices. The shipped file
  says `runsc`, so a control service or local-mode API whose Docker daemon lacks
  gVisor now refuses to start (`IsolationRuntimeError`) instead of silently
  using runc: before deploying, check that `docker info` lists `runsc`, or set
  `runtime: runc` deliberately. A local-mode API also starts its sandbox manager
  (pools, orphan reclaim, runtime images) at startup instead of on its first
  execution grading. Python callers pass
  `SandboxManager(..., runtime="runsc"|"runc")`; `is_missing_runtime_error` is
  gone. Sandboxes now have a read-only root filesystem: a submission or setup
  command that wrote outside `/app`, `/tmp` or `/dev/shm` (for example under
  `$HOME`) gets `EROFS`/`EACCES`; write to the workspace instead.
* **One execution time budget (COR-02).** `running_timeout` is now the host
  maximum: each sandbox lives the lifetime its caller asks for (a grading's
  `budget.session_seconds`) up to it, and stops itself then even if its owner
  died; containers no longer run `sleep infinity`. The shipped value rose from
  120 s to 900 s so that definitions of up to 26 thirty-second processes are
  granted; set it from the largest definition you accept. Omitting it now means
  900 s (it was 60 s), and values below 92 s are rejected at startup (the web host
  also refuses below 100 s, deliberate execution's budget). Definitions needing
  more are now refused at validation and acceptance (HTTP 422
  `EXECUTION_BUDGET_EXCEEDED`) instead of failing with `SANDBOX_ERROR` after the
  reaper fired. The acquire body gained the optional `lifetime_seconds`
  (`422 LIFETIME_EXCEEDED` above the maximum); an old client omits it and gets
  `running_timeout`. In remote mode the API reads the same `sandbox_config.yml`
  as the service; keep them identical. Custom evaluators declaring
  `sandbox_execution` must declare `process_timeouts`, and custom
  `HostCapabilities.execution` callables receive `(language, budget)`. Containers
  created before the upgrade still run `sleep infinity`: remove them with
  `python -m sandbox_manager.reclaim` after the old managers stop.

* **Single-transfer staging (PRF-03).** No configuration, wire or definition
  change. Staging no longer sends one `docker exec` per 48 KiB per file: a
  100-file submission went from 100 execs to one, 32 MiB of fixtures from about
  680 to one, and a grading's set of 100 fixtures from 100 to one through the
  `stage_fixtures` session call ([host capabilities](#host-capabilities));
  measurements are in the PRF-03 pull request. A failed staging operation now invalidates the sandbox (later operations answer `409
  SANDBOX_INVALIDATED`) instead of leaving a partially staged sandbox usable,
  and paths are validated before any file is staged. A fixture staged directly
  under `/tmp` no longer changes `/tmp` to `0755` (which stopped every later
  process from staging its run files). A custom runtime image needs `tar`, and
  the Docker daemon must be reached without TLS.
* **One sandbox budget (PRF-01).** `general.max_sandboxes` is required in
  `sandbox_config.yml`; the per-language `scale_limit` and `idle_timeout` are
  removed and rejected at startup with a message naming the replacement, as are
  unknown keys and `pool_size > max_sandboxes`. Set `max_sandboxes` from the
  sizing rule in [JOBS.md](JOBS.md#sandbox-capacity) (about 8 on 12 CPUs), not
  from the old sum of `scale_limit`s. `SANDBOX_MAX_HANDLES` is removed (the
  budget bounds handles) and the control service refuses to start while it is
  set; `429 HANDLE_LIMIT` no longer exists and saturation is `503
  CAPACITY_TIMEOUT` after the requested wait. Python callers construct
  `SandboxManager(pool_configs, client, max_sandboxes=N)` or
  `SandboxManager.from_config(SandboxHostConfig.load_from_yaml(path))`;
  `SandboxPoolConfig.load_from_yaml` is gone. `get_pool_stats()` no longer
  reports `scale_limit`/`utilization`; use `get_budget_stats()`. Upgrade the
  control service and its remote clients together (the acquire body gained
  `wait_seconds`; an old client gets no wait).

* **Process route (ARC-08).** `POST /sandboxes/{id}/run` and `/run-batch`
  are replaced by `POST /sandboxes/{id}/process`, whose body and response are
  the shared process contract (`ProcessRequestModel`/`ProcessResultModel`, see
  [PROCESSES.md](PROCESSES.md)). Clients of the old routes must upgrade
  together with the control service.
* **New required setting.** Set `SANDBOX_API_TOKEN` (a long random secret, for
  example `python -c "import secrets; print(secrets.token_urlsafe(32))"`) for the
  control service and every remote client (`web` settings; the GitHub Action
  no longer uses the control service). Compose fails fast when it is unset. Local development may set
  `SANDBOX_API_ALLOW_UNAUTHENTICATED=true` on the service instead.
* **Port no longer published.** Clients outside the Compose network can no
  longer reach port 8001. The healthcheck uses `/health`; `/stats` needs the token.
* **Removed Python APIs.** `release_sandbox(lang, sandbox)`,
  `destroy_sandbox(lang, sandbox)`, `LanguagePool.release`,
  `LanguagePool.destroy_sandbox`, `LanguagePool.acquire_sandbox`,
  `SandboxContainer.pickup/release`, `initialize_sandbox_manager`,
  `get_sandbox_manager` and `_register_shutdown_handlers` are gone. Use
  `manager.dispose(sandbox)` (or `with manager.acquire_sandbox(lang)`), construct
  `SandboxManager(pool_configs, client=None)` in the host and call `shutdown()`.
  `SandboxState.BUSY/STOPPED` became `ACTIVE/CLOSING/QUARANTINED/DISPOSED`.
* **Removed HTTP routes.** `DELETE /sandboxes/{id}/destroy` and
  `POST /sandboxes/{id}/request` are gone (pooled sandboxes have no network, so
  the request route could never succeed). `POST /sandboxes/{language}` now needs
  a JSON body with `request_id`. Errors use coded `detail` objects.
* **Remote client.** `RemoteSandboxManager(api_url, token=...)`; missing files
  raise `ArtifactNotFound`; unknown handles raise `SandboxHandleNotFound`.
* **Legacy containers.** Containers created before this change have no owner
  labels and are no longer removed at startup. After upgrading, stop old
  managers and run `python -m sandbox_manager.reclaim --legacy`.
* **Test isolation.** Tests no longer rewrite `LABEL_APP`; each test
  filters by its own owner id.

### Evaluator file declarations

Remove the unused `required_file`/`required_file_type` properties. Optional
`TestFunction` declarations are `file_extensions`, `minimum_files`,
`maximum_files`, `uses_context_files`, and `file_parameters`, plus the
`accepts_file(filename, language)` hook. Defaults allow zero or more scoped files
without a type restriction; the default hook honours `file_extensions`. Source
analysers override the hook with their parser rules (`source_files_only` was
replaced by `accepts_file`; the built-in static evaluators use
`structural_analysis.is_runtime_source`). Set
`maximum_files = 0` for endpoint-only checks; set matching extensions and minimum
and maximum of one for single-file checks. Avoid implementing declarations that
an evaluator does not need. The former internal structural pipeline step,
result container and accessor have been removed; the structural evaluator parses
its own selected sources. Selected files arrive as `evaluation.files` (with their
`metadata` and `changed_lines`); scope and a separate file-metadata mapping are
not passed to evaluators. The version 1 JSON shape is unchanged.

### Submission details

Clients previously reading `details.submission_files[name]` as a string must now
read `.content`. Legacy string-valued stored files project as objects with null
metadata and changed lines; they are not revalidated or assigned invented change
information. Old history retains its unverified provenance status.

### Catalog (INT-11, ONB-08)

ONB-08 removes the template-level `requires_sandbox` flag. The catalog wire
models drop `TemplateDescription.requires_sandbox` and
`EvaluatorDescription.requires_sandbox` (removed, not deprecated: the field
duplicated, and for mixed templates contradicted, `required_capabilities`).
Clients that read it use `"sandbox_execution" in required_capabilities` (or
`http_network` for API evaluators). `health_check` and `check_response_json`
now report `["http_network"]` instead of `["http_network", "sandbox_execution"]`.
Trusted Python callers build templates as `Template(name, description,
[evaluator, ...])` instead of subclassing with `tests`, `template_name`,
`template_description` and `requires_sandbox`, and import authoring types from
`autograder`. A subclass that still sets `tests` without calling
`super().__init__` is rejected as `INVALID_TEMPLATE` by compilation and
evaluation (discovery raises `TypeError`). Known external readers of the removed
field: `prisma-infrastructure/docs/grading-contract/v1/build_artifacts.py` and
`validate_definition.py` read `template.requires_sandbox`; they target the
legacy deployed image and must switch to evaluator `required_capabilities`
before they run against this version. `TemplateLibraryService` is replaced by the read-only
`autograder.template_library.BUILTIN_TEMPLATES` mapping; the package no longer
re-exports template classes. Definitions, stored snapshots and their hashes are
unchanged, so no database migration is needed.

The catalog response removes the redundant `available_tests` list. Consumers use
`evaluators[].identifier`; language constraints are per evaluator. Python callers
of the internal library's metadata methods now receive Pydantic models; serialize
with `model_dump(mode="json")`. The checked-in OpenAPI snapshot includes the new
models. Deploy catalog clients and server together if a client required the old
field. No database migration or definition schema-version change is needed.

Remove calls to the never-implemented `load_custom_template()` and pass instances
through `templates={...}` instead. All public definitions use `templates: [id]`;
comma-separated strings and plugin/source objects are rejected. The internal load
step now attaches compiled instances and performs no second registry resolution.

### Baseline comparison

* `autograder.services.result_comparator.ResultComparator`,
  `autograder.models.dataclass.comparison_result` (`ComparisonResult`,
  `TestDelta`) and `ResultTree.iter_test_results()` / `ResultTree.to_score_vector()`
  are removed. Use `compare_outcomes` on canonical outcomes and
  `outcome_score_vector` for ID-keyed vectors. The old comparator ignored
  definition revisions and always reported an overall delta.
* Result rows use `criterion_id` (formerly `path`), carry both labels and
  categories/effective weights, and add `reweighted`/`redefined` statuses.
* The unused `TestDeltaResponse` and `ComparisonResultResponse` web schemas are
  removed; the HTTP response model is `SubmissionComparisonResponse`.
* The arbitrary `baseline_result_tree` submission input remains removed.
* `submission_results.score_vector` and `submission_results.comparison` columns
  are legacy and unused: no code reads or writes them. They are kept to avoid a
  data-destroying migration; historical values are path-keyed and are never used
  for comparison.
* The terminal outcome v1 `comparison` enrichment field is unchanged. Normal
  grading leaves it `disabled`. An external host may still attest its own
  completed/failed enrichment, which is stored verbatim and not interpreted by
  this server; it is not the result of this operation.

### HTTP authentication (INT-01)

This is a breaking change for callers that used configuration creation,
configuration aliases, listing, submission creation, polling or history without
a token. Every such caller must send the integration token. Clients that only
read `/health`, `/ready` or `/templates` are unaffected. Examples in
`examples/` read `AUTOGRADER_INTEGRATION_TOKEN` from the environment.
Student-facing applications must proxy through the upstream application; do not
ship the integration token to browsers or student-controlled runners.

### Terminal outcomes

Operationally, v1 outcomes replace legacy duplicate `root`/`tree` and HTTP
`children` wrappers. Stored legacy results are not automatically attested with
current definition hashes. Consumers migrate to the canonical outcome plus
compact polling/history projections; source files and trees require explicit
trusted detail retrieval.

### Execution retry (COR-03)

Polling may stay `processing` for up to about 90 s more (defaults: 3
attempts, 30 s then 60 s) before a transient failure is published, instead of
reporting it at once; integrators that resubmitted on `retryable: true` can stop.
A deployment with a missing fixture bucket now fails those gradings with
`FIXTURE_PROVIDER_UNAVAILABLE` instead of `PREPARATION_ERROR`, and one with a
bad AI key or model with `PROVIDER_UNAVAILABLE` instead of a retryable
`PROVIDER_ERROR`. A published `retryable: true` means the host's retries are
exhausted.

## Discovery and trusted Python extensions

The typed template/evaluator catalog derives parameter schemas and validated
samples from the same contracts used by compilation. Capability requirements
and known language constraints live on evaluator implementations only; a
template is a named collection of evaluators with no requirements of its own.
The catalog's `requires_sandbox` field is removed rather than deprecated
(ONB-08): it restated `required_capabilities` and was wrong for a static
evaluator in an execution template. `BUILTIN_TEMPLATES` is the one built-in
registry, and the authoring types (error, process contract,
`BaseExecutionTest`) are part of the `autograder` facade. Discovery does
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
[execution contract](EXECUTION.md) for limits and
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
See [Python migration and execution order](../architecture/overview.md#run-order).

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
are unused legacy storage. See [baseline comparison](COMPARISON.md).

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
host's explicit runtime is its only variable (COR-04). The control API is private
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

## Language identity and its consumers (ARC-05)

`autograder.models.language.Language` is the only declaration of supported
language identifiers. It carries no image and imports no infrastructure. The
definition and outcome schemas, submission and deliberate-execution validation,
and the outcome's `language` derive from it, and wire identifiers are unchanged.
The host owns runtime images in the `runtimes:` map of `sandbox_config.yml`; an
allowed language without a profile is an unavailable capability
(`RuntimeUnavailableError`, control API `501 RUNTIME_UNAVAILABLE`, grading
`CAPABILITY_UNAVAILABLE`), never an invalid language. I/O evaluators own
`program_command` selection, with one documented `CMD` table; the
`CommandResolver`, its unused default table and its alias and file-name fallbacks
are removed. Analysis owns grammar selection (`structural_analysis.py`), and
evaluators decide their assessable files through `accepts_file`, so mixed
HTML/CSS/JavaScript submissions are parsed per file type. The HTTP submission
adapter still lower-cases its input language before binding. No plugin framework
was introduced. See [LANGUAGES.md](LANGUAGES.md) for the change surface.

## One process contract (ARC-08)

`ProcessRequest`/`ProcessResult` (`autograder/models/process.py`) are the only
way to run a process. A request has an explicit command mode: an exact `argv`, or
an explicit `shell` script run as `/bin/sh -c`. It also carries exact `stdin`
bytes, `cwd`, a process deadline and a per-stream output bound. Malformed quoting
is an error; it never switches to a shell, and definitions reject it when they
are compiled. A result is `exited` (any returned code), `timed_out` (killed by
the backend, with every process it started, before returning), or `not_started`
(missing executable). Transport, readback and invalidation failures are
exceptions. Classification uses only the exit status, so the language-specific
stderr classifier and the 137-means-timeout rule are removed. Preparation, the
I/O and artifact evaluators, and deliberate execution share the primitive and
keep their own policies. The local and remote backends were checked against each
other in real containers. `POST /process` replaces `/run` and `/run-batch`, and
process requests are never replayed. Output and artifact readback are bounded
where the process runs. See [PROCESSES.md](PROCESSES.md), which also gives the
migration from the old newline and shell behaviour.

## Bounded outcome text (COR-06)

Process output is bounded where the program runs, but the terminal artifact was
not. I/O reports copied whole streams, so a flooding program produced about
1 MiB per criterion. Student behaviour could then deny an Action's publication
(413) and enlarge HTTP storage. Reports (8 KiB) and feedback (256 KiB) are now
bounded in UTF-8 bytes by the outcome contract. Local text is excerpted once:
reports in `grade` and feedback in `render_feedback`. The excerpt is a
deterministic head and tail with a marker stating the full byte count. Attested
text above a bound is a typed validation error, never truncated. The worst-case
outcome is `CompiledDefinition.max_outcome_bytes`, a function of the criteria
count and of definition-authored text. Compilation keeps snapshot plus outcome
within 24 MiB. Assessment, scores and schema shape are unchanged; only report
text above a bound changes. Definitions above the budget (more than about 465
criteria) now fail with `DEFINITION_TOO_LARGE`, including stored ones when they
are loaded. That includes a job accepted before the deployment whose bound
snapshot is over the budget: its worker compilation fails and the job ends as a
failed outcome. This departs from "activation gates new acceptance, not bound
jobs". It is accepted because such a definition (more than about 465 criteria
with short parameters) is not a realistic assignment.

Migration evidence: outcomes stored before the bounds are upgraded in place by
Alembic revision `009_bound_outcome_text`, which applies the engine's excerpt to
every stored report and feedback. Unpublished receipts get the same excerpt when
they are read, so pending delivery retries finish. Both use one function,
`bound_outcome_text`, and leave scores unchanged.
`tests/web/test_outcome_text_migration.py` stores pre-bound rows and a pre-bound
receipt, then checks `/details`, comparison and receipt replay through the real
app. An Action `delivery.json` saved by an earlier release is an attestation, so
an oversized report in it is rejected with `text_too_large`, not excerpted. The
excerpt marker is fixed English until ONB-03. See
[OUTCOMES.md](OUTCOMES.md#size-bounds).

## Versioned runtime images (ENV-04, runtime part)

The student runtimes are built from `sandbox_manager/images` on digest-pinned,
supported bases (CPython 3.13, Temurin JDK 21, Node.js 24, GCC 15 on Alpine
3.24) without a build context, and hold no package manager, downloader or setuid
binary. Each image's reference is derived from its Dockerfile's content, CI
publishes a reference once and never overwrites it, and `sandbox_config.yml`
names exactly those references; floating local `:latest` tags are gone. A
`SandboxManager` never pulls: it starts only when every configured image is
present and declares its language in the `autograder.runtime.languages` label,
and raises `RuntimeImageError` otherwise. Hosts therefore pull or build the
configured images before starting; an old unlabelled image is rejected rather
than silently used. See [LANGUAGES.md](LANGUAGES.md#runtime-images).

## Lean service and Action images (ENV-04)

The API, sandbox manager and Action each have an image that holds only what its
process imports: locked runtime dependencies (`server`, the new `sandbox` extra,
or the base dependencies) in `/opt/venv` and an allow-listed set of first-party
directories in `/app`, on a digest-pinned `python:3.13-slim` base. The API and
sandbox manager images no longer share contents: the sandbox manager has no web
or database stack. No image has `dockerd`, `containerd`, a Docker CLI, Node.js,
curl, uv or a test tool. The build context is an allow-list (`.dockerignore`),
so `.env`, `.venv`, `data/` and caches never enter an image. `action.yml` pins
a prebuilt image instead of building `Dockerfile.actions` in every job; which
image, and how it is published, is
[ENV-07](#images-published-from-verified-main-no-releases-before-100-env-07)
(ENV-04's versioned release before each merge and its `action-check` gate are
retired). `tests/images/` (`make test-images`, CI) checks the built images,
including a build from a checkout with planted secrets and the Action grading
the static example.

Migration: Compose health checks use Python instead of curl. Deployments that
run `curl` inside the API or sandbox manager containers must do the same. The
Action image no longer contains Node.js or `tree`.

## Closed locale and outcome-code vocabularies (COR-07)

`Locale` (`autograder/models/locale.py`) is the one declaration of supported
locales; `parse_locale` (case-insensitive, `_` read as `-`) is the only way a
boundary accepts one. `Submission`, the HTTP schema (422, OpenAPI enum) and the
Action CLI (argument error) all use it, and unknown locales are rejected rather
than replaced by English. The translator loads one catalog per declared locale at
import, so no caller value becomes a file path; the lazy loader, its per-lookup
error logging and the singleton are removed. Outcome error codes are the closed
`OUTCOME_ERROR_CODES` enum: engine codes, which `EvaluationError` enforces at
construction, plus host-only `RECOVERY_EXHAUSTED`, `RECOVERY_INPUT_UNAVAILABLE`
and `LEGACY_UNVERIFIED`. `EXECUTION_ERROR` is the single unexpected-failure code;
the HTTP host's `EXECUTION_FAILED` is removed and migrated (revision 010). A
contract test enumerates every emitted code from the source and requires the
OUTCOMES matrix and both schemas to list exactly that vocabulary.

## One host-wide sandbox budget (PRF-01)

Execution capacity is one number per sandbox manager, `general.max_sandboxes`
(N). Every language pool shares one `SandboxBudget` whose lock is also the pools'
lock; a slot is held from the start of creation (or the hand-out of a warm
container) until Docker confirms removal, so creating + active + closing +
quarantined ≤ N. Saturation waits in one FIFO queue for the caller's
`wait_seconds` (grading 600 s, deliberate execution 10 s) instead of failing;
expiry is `SandboxCapacityTimeout`, reported to grading as a retryable
`CAPABILITY_UNAVAILABLE` and to deliberate callers as `503 EXECUTION_BUSY`.
Docker create/remove run outside the lock. Warm idle containers stay outside N
and never exceed `pool_size`, so `idle_timeout` had nothing left to expire and
was removed with `scale_limit` and `SANDBOX_MAX_HANDLES`; startup rejects them.
The control API waits for slots in its own threads so waiting acquisitions
cannot starve the `DELETE` that frees one, and no longer serializes acquisitions.
No new pool abstraction or scheduler was added. See [SANDBOX.md](SANDBOX.md) and
[JOBS.md](JOBS.md#sandbox-capacity).

## Who ended a sandbox (COR-01)

A container that stopped under a process no longer keeps that process's exit
code: the reaper or `docker kill` had turned correct programs into zeros, and a
submission could kill the `sandbox`-owned PID 1 or collector to turn a bad grade
into a retryable `SANDBOX_ERROR`. PID 1 (Docker's init) and the control execs
that run beside the submission now run as `root` with only `KILL` and
`DAC_OVERRIDE`; submission processes run as `sandbox` without capabilities
(`no-new-privileges`) and are the OOM killer's first choice. Attribution uses
host-side evidence only: the container's cgroup counters (runc), the pool's
disposal record and Docker's record of how the container stopped. Host stops
and removals are infrastructure failures. Memory or process exhaustion is the
core `SandboxExhausted` (control API `409 SANDBOX_EXHAUSTED`), not a
`RuntimeError`; because gVisor's container stops while runc's survives, the
sandbox is spent under both runtimes and the exhausting criterion and every
later one are assessed zeros. A missing or non-executable workspace program is
an assessed zero; only a runtime command that cannot start stays
`PROCESS_START_FAILED`. Artifacts and outputs are read whatever permissions the
submission set, never through a symbolic link it planted (a link is no
artifact, under both runtimes). The collector needs no fork until it has
reported the cgroup counters, is restarted when runc finds no pid to start it,
and a running container at its pids limit is exhaustion. The outcome wire is
unchanged. See [PROCESSES.md](PROCESSES.md#who-ended-a-run).

## Explained submission failures (ONB-02)

INT-07 hid infrastructure details from outcomes and, with them, the diagnostics
students own: a non-compiling submission said only "A required setup command
failed." A `submission`-category `EvaluationError` may now carry an
`explanation` (a `preflight.error.*` catalog key and its parameters) and the
failing step's `output`. The pipeline renders the explanation in the
submission's locale (COR-07's closed set) as the error `message` and excerpts
`output` with COR-06's `bound_text` and `MAX_REPORT_BYTES`; `EvaluationError`
and `OutcomeError` reject both for every other category, so capability,
provider and internal errors are unchanged byte for byte. Categories, codes,
`retryable` and the null score/tree are unchanged: an unpreparable submission is
still a failed grading, never an assessed zero.

The wire change is additive: `OutcomeError.output` is optional and absent (not
`null`) when there is none, so every outcome without it serializes exactly as
before, and stored outcomes need no migration. A consumer that validates with
`additionalProperties: false` against the previous schema must update before it
receives an outcome with `output` or a snapshot with `private_output`: deploy
the HTTP host before Actions that attest them. Setup commands gain `private_output` (strict boolean,
default `false`), omitted from the canonical snapshot while `false`, so existing
definition hashes and bound snapshots are unchanged. Messages name only
definition-authored files, steps, criteria and languages, never the setup
command or submitted file names. The dead `preflight.*` and `system.*` catalog
keys were replaced by the keys now used; a test keeps that namespace free of
unused or missing keys in both locales. See
[OUTCOMES.md](OUTCOMES.md#explained-submission-failures).

## One execution time budget (COR-02)

Four unrelated clocks bounded a grading (per-process deadlines, the reaper's
`running_timeout`, an unbounded HTTP lease and `sleep infinity`), so a legitimate
worst case longer than `running_timeout` failed with `SANDBOX_ERROR`, and a
crashed owner left its student processes running until something reclaimed
them. Now compilation derives one `ExecutionBudget` from deadlines already
declared (evaluator `process_timeouts`, 30 s per setup command; no authoring
field), and the one host knob is the maximum `running_timeout`. A budget the host
cannot grant is refused before any code runs (`EXECUTION_BUDGET_EXCEEDED`; HTTP
422 at validation and acceptance, never after queueing). Each granted sandbox
arms its own lifetime with a root exec the submission cannot signal and stops
itself then, whatever happens to its owner; owner-lease reclamation only removes
stopped records. Every process runs before the one AI call, so the sandbox
lifetime holds only process time. An HTTP attempt's deadline is the session
lifetime from the grant plus the provider deadline per AI call plus a margin; it
ends as a retryable `ATTEMPT_DEADLINE_EXCEEDED` without further lease renewal,
retried within the attempt budget since COR-03. See [SANDBOX.md](SANDBOX.md#sandbox-lifetime),
[CAPABILITIES.md](CAPABILITIES.md#execution-budget) and
[JOBS.md](JOBS.md#attempt-deadline).

## The default report explains the rubric and the score (ONB-03)

The `default` Markdown report was a flat list per category with a Python repr
of every parameter, `Score: 0.0/100` per test and fixed headings ("❌ Points to
Improve" even when no penalty applied). It now follows the authored tree
(category, nested subjects, tests) under the authored names, and states the
points every category, subject and test moved the final score: base and
penalty points lost, bonus points earned, and the equation
`100 − base − penalty + bonus = final`, noting when the 0–100 limit applied.
The values come from the shared scoring module: `criterion_points` (next to
`final_score`) for categories and focus's per-test `points`; the reporter
aggregates them and recomputes nothing. Parameters are never rendered; a test
shows its status, file target, score, points and its evaluator's report, so a
value appears only when the evaluator chose to report it. Headings carry only
the neutral category name (or the authored `category_headers`) and numbers.
Preferences are unchanged: `show_score: false` hides every number,
`show_passed_tests` lists passing tests (otherwise a fully passing holder says
so in one line), `add_report_summary` controls the summary table. The
formatter module and the unused translation keys are removed. The report is
still a pure function of tree, preferences and locale, and the outcome wire is
unchanged; the Markdown text is a breaking change for anyone parsing it
(goldens: `tests/unit/services/feedback_golden/`,
`tests/integration/canonical_outcome_golden.json`).

## Bounded writable paths and an explicit runtime (COR-04)

The root filesystem was writable, so a submission writing fsynced files with the
page cache dropped grew a sandbox's writable layer on host disk (540 MB under
runc, 1 GiB under gVisor within the probe's time) on the VPS it shares with
PostgreSQL. Sandboxes now have a read-only root filesystem; the writable paths
are tmpfs mounts (`/app` 64 MiB, `/tmp` 32 MiB, `/dev/shm` 64 MiB) charged to the
memory limit, plus runc's in-kernel `/dev/mqueue`, so the per-sandbox host-disk
bound is 0 bytes. Any error
mentioning `runsc` used to switch a pool to runc for the rest of its life. The
runtime is now the host's explicit, required `general.runtime` (`runsc` or
`runc`), verified and logged when the manager starts; a failed gVisor start
fails that one acquisition and never downgrades. Migration: the shipped
configuration says `runsc`, and a daemon without gVisor stops the service at
startup, loudly, before it reports ready: the control service in its lifespan
and a local-mode API (production's current shape) in its own startup, which now
builds its sandbox manager there instead of on the first execution grading. A
deployment checks that `docker info` lists `runsc` or deploys `runtime: runc`
deliberately; that check is a precondition of the `refactor/363` release. SANDBOX.md alone states the per-environment
runtime and Docker-socket exposure, names the supported internet-facing
topology (remote mode, socket only in the private control service), and maps
each isolation guarantee to the hostile-submission test that pins it under each
runtime; CI's isolation job installs the pinned gVisor release so both run. See
[SANDBOX.md](SANDBOX.md#isolation-profile-and-runtime).

## Action execution on the runner (ENV-03)

The published Action could not grade any execution-based criterion: with no
mode set, its host defaulted to a remote sandbox service at `localhost:8001`
that nothing provides, so every I/O, command or setup criterion failed as
`CAPABILITY_UNAVAILABLE`. `DockerHost.from_environment()` and that default are
deleted; `DockerHost` now requires an explicit `mode`, and `mode="remote"`
requires the control API URL.

**Decision.** The Action runs submissions on the GitHub runner's own Docker, in
the web host's single sandbox profile (`sandbox_manager/docker_profile.py`: no
network, all capabilities dropped for the unprivileged `sandbox` user,
`no-new-privileges`, memory/CPU/pids/file-size limits, read-only root with
memory-bounded tmpfs writable paths, no bind mounts, no environment from the
Action). GitHub-hosted runners have no gVisor, so the Action's host explicitly
requests `runc` (`execution_host.runner.RUNNER_RUNTIME`) on every runner; the
web host's `general.runtime` does not apply to it. As for every host since
COR-04, the manager verifies at construction, before grading, that the daemon
offers that runtime, and never switches to another. Each sandbox stops itself
when the grading's execution budget (COR-02) ends; the host maximum is
`sandbox_config.yml`'s `running_timeout`, and a definition needing more is
refused with `EXECUTION_BUDGET_EXCEEDED` before any code runs. #363 allowed the runner VM
itself as the boundary, but running submissions directly in the Action container
would put them beside the Action's environment (`ACTIONS_RUNTIME_TOKEN`, the
cloud token, provider keys) and the mounted Docker socket, which breaks the
[trust table](../github_action/trust.md#runner-execution-boundary). Under `runc`
the kernel is shared, so the boundary is Linux namespaces, cgroups, seccomp and
the dropped capabilities; a kernel escape would reach the runner VM, which
GitHub discards after the job. Self-hosted runners keep the
`trusted-self-hosted-runner` rule for publication.

**Host shape.** `execution_host.runner.RunnerHost` serves only the language the
definition selected: one sandbox, created when the grading acquires it (budget
1, `pool_size` 0), from the image `sandbox_config.yml` pins, pulled by the Action
when the runner lacks it. There is no warm pool, control API, orphan reclamation
or `SANDBOX_*` setting; those stay web-only. The Action constructs the host only
when the selected language's criteria or preparation execute code; static and
AI-only definitions never touch Docker. Construction checks Docker before
grading: without a reachable daemon the Action fails with the documented
`Docker is not available to the Action` error and writes no outcome, instead of
grading to `CAPABILITY_UNAVAILABLE`
([Requirements](../github_action/README.md#requirements)). Grading runs in a
worker thread while the main thread waits, so `SIGTERM` (turned into
`SystemExit` by `main`) interrupts only that wait; the host is then closed,
removing the sandbox (and a container still being created) before the process
exits, and on every other path before anything is retained or published.

**Pinning.** The Action image ships `sandbox_config.yml`, so each published
Action image pins its runtime image references (content-addressed tags, never
`:latest` or a local-only tag), and `main` publishes those runtime images with
it ([ENV-07](#images-published-from-verified-main-no-releases-before-100-env-07)).

**Verification.** The `Packaged Action on a hosted runner` job in `verify.yml`
runs `uses: ./` on `ubuntu-latest` (static, Python I/O, C I/O, a wrong answer
and a credential probe) and checks outcomes, outputs, one sandbox per execution
run and none left over (`scripts/action_fixtures.py`). `tests/images/` runs the
packaged image with the runner's socket: single-runtime provisioning, removal
on success, failed grading and `SIGTERM`, the probe, the missing-Docker error
and the pull of an absent runtime image.

Migration: workflows need no change; execution-based definitions now grade on
Linux GitHub-hosted runners with no extra step. Workflows that set
`SANDBOX_MODE`, `SANDBOX_API_URL` or `SANDBOX_API_TOKEN` for the Action can drop
them; they are ignored. Runners must provide Docker (all Linux GitHub-hosted
runners do; macOS and Windows runners cannot run container actions at all). Each
runtime package on GHCR must be public for the Action to pull it. Python callers of `DockerHost()` must pass `mode`, and `mode="remote"` an
`api_url`.

## Images published from verified main; no releases before 1.0.0 (ENV-07)

The maintainers decided there are no releases until the refactor is complete;
the first is 1.0.0. ENV-04's flow (a versioned image released from a branch
before it merges, and the `action-check` gate failing `main` until it was) left
`action.yml` on `main` naming `autograder-action:0.6.0`, which was never
published, so every `webtech-network/autograder@main` workflow failed to pull
it and every pull request into `main` was red. Automated deployment of the API
to a VPS is retired as well.

`main` is now the channel. In `.github/workflows/verify.yml`, the `publish`
job (`Publish images from main`) needs every verification job and runs only
for pushes to `main`. It rebuilds and checks the images from that commit
(`make test-images`, `make sandbox-build-all`) and runs `make publish-images`
(`scripts/publish_images.py`), which publishes nothing unless the commit is
still the head of `origin`'s `main`, then pushes the runtime images not yet
published (content-derived references, never overwritten), then the API,
sandbox manager and Action images as `sha-<commit>` (immutable) and `main`
(moving), and confirms each with the registry as the workflow token sees it.
Publications run one at a time (`publish-main` concurrency group). `action.yml`
runs `docker://ghcr.io/webtech-network/autograder-action:main`. A test ties
that reference to what the script publishes, and frame tests check the job
graph: publication needs every verification job, no job deploys, uses a
secret other than `GITHUB_TOKEN`, tags, releases or runs the retired
`action-check`, and only the `publish` job can push images. `sandbox-images.yml`
is folded in: its pull-request run duplicated the `docker` job, and its
publication is this job's first step. The images carry
`org.opencontainers.image.source`, so GHCR links each package to this
repository and the workflow token can push it. No check depends on a release
or on package visibility: a still-private package is a warning of the publish
job, never a red pull request.

`@main` reads `action.yml` from the head of `main` but runs the image of the
newest verified commit, so while a commit is being verified the two can differ
by that commit; a commit that fails verification publishes nothing. Before
1.0.0 no `uses:` ref is reproducible: every ref runs `:main`. The 1.0.0 release
re-tags a verified commit's `sha-<commit>` images as `1.0.0` and tags a commit,
outside `main`, whose only change pins `runs.image` to that version
([Releases](../github_action/README.md#releases)).

Migration: consumer workflows need no change. An organization admin makes each
package public once, after `main` first publishes it (`autograder-action` and
every `autograder-sandbox-<name>` for runners; `autograder-api` and
`autograder-sandbox-manager` if deployments pull anonymously). The `Deploy API`
job, its secrets (`SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`,
`DEPLOY_PATH`, `GHCR_PULL_TOKEN`) and the `autograder-api:latest` tag are gone:
operators upgrade by hand ([Upgrade runbook](../operate/deployment.md#upgrade-runbook))
from a published `sha-<commit>`, and the repository secrets can be deleted.
The `Release Action image` and `Deploy API` jobs leave the publication side of
the [required checks](../guides/development.md#required-checks); the required
verification jobs are unchanged.

## Retryable failures of accepted work are retried (COR-03)

The engine marked transient failures `retryable: true`, but the HTTP worker
published every finalized outcome, so a sandbox service restart, a capacity wait
that expired or a provider outage became a terminal `failed` grade on the first
attempt; the attempt budget covered only interrupted attempts. The flag also lied
the other way: a missing fixture bucket or a denied credential was a retryable
`PREPARATION_ERROR`. Now `retryable` means "can pass without an operator": the
S3 fixture provider reports a store that refuses the bucket or the credentials as
the non-retryable `FIXTURE_PROVIDER_UNAVAILABLE` (an unset bucket supplies no
provider at all), and the Docker host reports a missing runtime or a refused
sandbox-service token as a non-retryable `CAPABILITY_UNAVAILABLE`. The OpenAI
provider reports a refused key, access or model (HTTP 401/403/404) as the
non-retryable `PROVIDER_UNAVAILABLE` and other deterministic 4xx answers as a
non-retryable `PROVIDER_ERROR`; transport failures, deadlines, 408/409/429 and
5xx stay retryable. The HTTP
worker is the one retry layer: a retryable failure with budget left releases the
claim (fenced by the attempt UUID, the row stays `processing` with no owner) for
`WEB_RETRY_SECONDS` × 2^(attempt − 1); the last attempt of `WEB_MAX_ATTEMPTS`
publishes the engine's failure. Assessed results and non-retryable failures
publish on the first attempt. The fixture client makes one request per fixture
(no SDK retries). No wire, schema or engine change; see
[JOBS.md](JOBS.md#execution-retry) and the
[migration note](#execution-retry-cor-03).

## Releases re-tag verified images (REL-01)

A release is cut by hand, once, from a commit `C` of `main` whose `publish`
job succeeded: the Release workflow (`.github/workflows/release.yml`, `make
release`, `scripts/release.py`) re-tags `C`'s `sha-<C>` images as the version,
by digest and without rebuilding, then tags a commit on top of `C`, outside
`main`, whose only change pins `action.yml`'s `runs.image` to that version, and
creates the GitHub Release with the version's `CHANGELOG.md` section as notes
([Releases](../github_action/README.md#releases)). Rebuilding at release time
would ship bytes nothing verified, and pinning `runs.image` on `main` would make
`@main` run a release instead of the newest verified commit, so the pin lives
only in the tagged commit. The workflow runs only on `workflow_dispatch` from
`main`; the script checks every precondition before it changes anything and
refuses a commit not on `main`, a commit without a successful publish job or
`sha-<C>` images, a version `pyproject.toml` does not declare or the changelog
does not describe, an existing tag, and an existing image tag with other bytes.
An image tag identical to `sha-<C>` (an interrupted run of the same release) is
kept, so a re-run completes it.

`sha-<commit>` is now immutable in fact: the `publish` job pushes it only when
the registry does not have it and moves `main` to that manifest in the registry
(`docker buildx imagetools create --prefer-index=false`, which keeps the digest),
so re-running the job for a commit cannot change what a release re-tags, and
`main` always serves the bytes of its `sha-<commit>`.

The version is declared once in `pyproject.toml`; `autograder.__version__`,
the HTTP API (health and OpenAPI) and the sandbox control API report it, and a
test keeps them equal. [STABILITY.md](STABILITY.md) states what a version
promises. Frame tests check that the release workflow is dispatch-only, runs
from `main` and only `make install` and `make release`, and that only it and the
`publish` job can push images; script tests run against real git repositories
with the registry and `gh` faked at the subprocess boundary.
