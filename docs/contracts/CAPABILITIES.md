# Host capabilities and preparation

The grading engine accepts `HostCapabilities` through `build_pipeline` or
`evaluate_submission`. Providers are borrowed: callers may share them between
runs and retain responsibility for their lifetime. An execution factory returns
one owned `ExecutionSession` for one run. Ownership transfers when the factory
returns, before file staging. The pipeline closes that session once on every
subsequent path, then constructs its immutable terminal outcome. Failed
acquisition transfers nothing. Cleanup errors are logged and preserve a completed
grade; hosts can inspect their infrastructure logs and dispose their manager.
The Docker session's `close()` raises when sandbox removal is not confirmed; the
sandbox stays quarantined in its pool for bounded retry and pool statistics.
Never publish until the pipeline has returned.

The engine first selects the language, validates required preparation files and
every criterion's file contract without provider calls, and computes one
requirement set. This set uses selected evaluator instances and preparation for
the selected language, read only from each evaluator's own declaration. Unused
evaluators, static evaluators in an execution template and another language's
setup do not request resources. Fixtures apply to the definition's selected run.
Discovery uses the same evaluator capability declarations and never probes
availability. Missing execution support has a capability error; a disallowed
language has a separate submission error. A host that supports execution but has
no runtime profile for the bound language (no `runtimes:` image) also fails with
`CAPABILITY_UNAVAILABLE`; see [LANGUAGES.md](LANGUAGES.md).

## Execution budget

The same requirement set carries the run's `ExecutionBudget`, derived only from
deadlines already declared (there is no authoring field): each selected
evaluator declaring `sandbox_execution` lists the deadline of every process one
assessment may run in `process_timeouts` (the public `BaseExecutionTest`
declares its one 30 s run; registration rejects an execution evaluator without
the declaration), and each setup command of the bound language adds its 30 s
`SETUP_TIMEOUT_SECONDS`. `budget.process_seconds` is their sum and
`budget.processes` their count; `budget.ai_calls` is 1 when any AI criterion is
selected (one provider call for all of them). A session must live
`budget.session_seconds` = process seconds + 2 s per process + 60 s per session
(`PROCESS_ALLOWANCE_SECONDS`, `SESSION_ALLOWANCE_SECONDS`) for starting and
collecting processes and for staging and cleanup.

`HostCapabilities.execution(language, budget)` returns a session that lives at
least `budget.session_seconds` from its grant, and ends itself then. A host
states the longest session it grants in `HostCapabilities.max_session_seconds`
(`None`: no stated maximum); before any provider call the engine refuses a
longer budget with `capability / EXECUTION_BUDGET_EXCEEDED`, not retryable, and
a host that refuses at acquisition raises that same `EvaluationError`. Every
process of the run executes before the one provider call, so the provider's own
deadline (`AssessmentProvider.deadline_seconds`) is never part of the session.
The Docker host's maximum is `running_timeout` in `sandbox_config.yml`
([SANDBOX.md](SANDBOX.md#sandbox-lifetime)); HTTP hosts also check it at
validation and acceptance and derive each attempt's deadline from the same
budget ([JOBS.md](JOBS.md#attempt-deadline)).

`ExecutionSession` provides submission staging, process execution
(`run_process`, see [PROCESSES.md](PROCESSES.md)), relative artifact readback,
fixture staging and disposal. Its `fixture_root` declares the
host's fixture root; `stage_fixtures(fixtures)` receives the definition's whole
fixture set at once as `StagedFixture(path, content, read_only)` values with
relative paths, so a host can stage it in one transfer (the Docker host makes one
`inject_assets` call). Core fetches every fixture before staging any, calls
`stage_fixtures` once and only when the definition declares fixtures, and an
implementation stages the whole set or raises. Fixture references remain logical
and the supplied resolver returns bytes, including empty bytes. Core does not select S3 credentials, Docker managers,
OpenAI clients, secrets or provider models. Concrete shared host composition lives
under `execution_host/`.

## Fixture providers

`HostCapabilities.fixtures` is a callable `reference -> bytes`. It receives only
the logical reference: destination path and read-only mode are placement and are
applied by `ExecutionSession.stage_fixtures`. `b""` is valid content. A provider
raises `autograder.models.capabilities.FixtureNotFound` when the reference has no
object; any other exception is a provider failure. Both stop preparation with the
same safe `capability / PREPARATION_ERROR` outcome; a missing fixture is not
retryable, a provider failure is. Raw provider errors stay in host logs.

The Docker host composes `execution_host.fixtures.S3FixtureProvider` from
`EXTERNAL_ASSETS_BUCKET_NAME`, `S3_ENDPOINT_URL`, `AWS_REGION` and
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` ([configuration](../operate/configuration.md)).
Configuration is captured at host construction, where an endpoint without a
bucket or half a credential stops the host; one SDK client is created on the
first selected fixture and reused. Missing keys (`NoSuchKey`/404)
are `FixtureNotFound`; missing buckets, access denials, transport errors and an
unset bucket are provider failures. Deliberate execution `assets` use the same
host provider.

There is no fixture cache. Every run reads the current object for each reference,
so distinct references (for example `a/b` and `a_b`) cannot alias, replacing an
object needs no invalidation, and no process writes cache files. The former
in-memory/disk cache (`EXTERNAL_ASSETS_IN_MEMORY_CACHE_LIMIT`,
`/tmp/autograder_assets_cache`) was removed because no measurement established a
latency or cost benefit; a host that needs one must key it by full provider
identity (endpoint, bucket, key and object version), write atomically, and
document invalidation, size and lifetime.

The public `Preparation` model is consumed directly. `runtime_setup` and the
permissive parallel `SetupConfig` parser have been removed. Definitions continue
to use `preparation.languages.<language>.required_files`, typed named
`setup_commands`, and `fixtures` with logical `reference` and relative `path`.
Docker maps fixtures to `/tmp/app/<path>` and artifacts to the submission root
`/app`. Commands that read fixtures must use the host's declared root. Preparation
runs after acquisition and fixture staging; a failed command stops assessment
with no score or tree.

## Static, I/O, AI and API examples

Static assessment needs no capabilities:

```python
outcome = evaluate_submission(submission, definition=static_definition)
```

HTTP and Actions use the same I/O definition with an explicitly composed Docker
profile. `DockerHost` constructs its own local or remote manager on its first
acquisition; static work does not initialize it. HTTP owns the host for its
application lifetime and calls `DockerHost.start()` at startup, so a local-mode
API whose sandbox configuration, runtime or images are unusable refuses to start.
Actions owns it for the command and closes it before publication. HTTP defaults
to its configured local profile; the container Action defaults to remote execution
at `http://localhost:8001` and should set an accessible service URL explicitly:

```python
from execution_host.docker import DockerHost

host = DockerHost(mode="remote", api_url="http://sandbox-manager:8001")
try:
    outcome = evaluate_submission(
        submission, definition=io_definition, capabilities=host.capabilities
    )
finally:
    host.close()
```

A complete shared definition is checked in at
`examples/contracts/input_output.json`.
Use it as the HTTP configuration's `definition` and as the Action's
`definition-path`. Both assess `main.py` containing `print(input())`, sending
`hello` on stdin and expecting `hello` on stdout. HTTP accepts that file through
its submission endpoint; Actions collects it from `submission-root`.

The Actions container can use an accessible sandbox service through
`SANDBOX_MODE=remote`, `SANDBOX_API_URL` and `SANDBOX_API_TOKEN`; this avoids
requiring a nested Docker daemon. The control service is private and token
protected; see [SANDBOX.md](SANDBOX.md) for its lifecycle, owner leases,
worker model and recovery rules. Local Docker hosts use `mode="local"` and a sandbox configuration file.
Custom runner implementations implement the same session operations; evaluators
receive no manager or provider identity. Only evaluators declaring `sandbox_execution`
or `http_network` receive the session, as `evaluation.session`; every other
evaluator receives `None`, and AI evaluators never receive the provider. There is no unrestricted runner profile
shipped by this change.

AI providers implement `run(tests, submission_files, locale)` and return exactly
one finite `TestResult` per criterion ID. A trusted Python host can inject a
provider without credentials or network access, for example:

```python
from autograder.models.capabilities import HostCapabilities

outcome = evaluate_submission(
    submission, definition=ai_definition,
    capabilities=HostCapabilities(ai=my_assessment_provider),
)
```

The executable offline example
`examples/contracts/host_provider.py`
registers a trusted AI evaluator and injects a demonstration provider. Run it with
`python -m examples.contracts.host_provider`; replace the canned provider for real
assessment.

Each prompt receives its selected assessment files. The provider additionally
receives all submitted file contents as context, including files outside the
evaluation scope. Scope controls assessment, not privacy or upload selection.
Hosts must collect only files appropriate for that provider. Standalone AI
evaluators do not create a provider or retry missing batch results.

### The shipped OpenAI provider

`execution_host.docker.ConfiguredAssessmentProvider` reads `OPENAI_API_KEY` (or,
with `ENVIRONMENT=production`, the AWS secret `AUTOGRADER_AI_SECRET_NAME`) and
optional `AUTOGRADER_AI_MODEL` when the host is composed, but resolves nothing
until the first selected AI criterion. Static and I/O gradings never look up
credentials, construct a client or touch the network.

- **One client per host.** The credential lookup and the SDK client (with its
  connection pool) happen at most once per host lifetime, also when several
  workers reach the first AI grading at the same time. A failed lookup or
  construction is `PROVIDER_UNAVAILABLE` and is not cached: the next AI grading
  tries again.
- **Secret rotation needs no restart.** A request rejected as unauthenticated
  (HTTP 401) fails that grading with `PROVIDER_ERROR` and drops the client; the
  next AI grading looks the secret up again.
- **Deadline.** `openai_client` sets an explicit deadline and zero SDK retries
  (the SDK defaults are a 600 s read and two retries). Each network wait is
  bounded by `REQUEST_TIMEOUT_SECONDS` (180 s; connecting by
  `CONNECT_TIMEOUT_SECONDS`, 10 s), and a grading makes one request, so a
  provider that stops responding fails the grading with the safe, retryable
  `PROVIDER_ERROR` within 190 s. These constants in
  `execution_host/openai_provider.py` are the AI term of any attempt deadline.
- **No hidden retries.** A timeout, 429, 5xx or any other failure is exactly one
  request. Whether to try the grading again is the host's decision, not the SDK's.

`AssessmentProvider.assess(requests, *, context_files, locale)` receives one
batch of `AssessmentRequest(criterion_id, prompt)` and returns a sequence of
`ProviderAssessment(criterion_id, score, report)`, one per request. The engine
(`assess_many`) validates exact ID coverage and every score: unknown, duplicate,
missing or invalid answers fail the required grade, and nothing is retried.

API assessments require `server_execution`, a factory returning a
`ServerSession`: staging/setup precede `start_server()` and `wait_ready()`, HTTP
requests use `make_request()`, and `close()` owns teardown even after startup or
readiness failure, including `stop_server()`. The host selects server startup configuration and readiness
policy. Current Docker pools disable network and provide no server lifecycle;
therefore their API outcomes fail with `SERVER_CAPABILITY_UNAVAILABLE` before
acquisition or scoring. Ordinary I/O pools do not gain network access. A host
that supports API assessment must supply the complete server profile explicitly.

## Migration

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

## Earlier architecture issues

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
