# Host capabilities and preparation

The grading engine accepts `HostCapabilities` through `build_pipeline` or
`evaluate_submission`. Providers are borrowed: callers may share them between
runs and retain responsibility for their lifetime. An execution factory returns
one owned `ExecutionSession` for one run. Ownership transfers when the factory
returns, before file staging. The pipeline closes that session once on every
subsequent path, then constructs its immutable terminal outcome. Failed
acquisition transfers nothing. Cleanup errors are logged and preserve a completed
grade; hosts can inspect their infrastructure logs and dispose their manager.
Never publish until the pipeline has returned.

The engine first selects the language, validates required preparation files and
every criterion's file contract without provider calls, and computes one
requirement set. This set uses selected evaluator instances and preparation for
the selected language. Unused execution templates and another language's setup
do not request resources. Fixtures apply to the definition's selected run.
Discovery uses the same evaluator capability declarations and never probes
availability. Missing execution support has a capability error; a disallowed
language has a separate submission error.

`ExecutionSession` provides submission staging, process execution, relative
artifact readback, fixture staging and disposal. Its `fixture_root` declares the
host's fixture root; `stage_fixture(path, bytes, read_only)` receives a relative
path. Fixture references remain logical and the supplied resolver returns bytes,
including empty bytes. Core does not select S3 credentials, Docker managers,
OpenAI clients, secrets or provider models. Concrete shared host composition lives
under `execution_host/`.

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
profile. `DockerHost` lazily constructs its own local or remote manager; static
work does not initialize it. HTTP owns the host for its application lifetime.
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
`SANDBOX_MODE=remote` and `SANDBOX_API_URL`; this avoids requiring a nested Docker
daemon. Local Docker hosts use `mode="local"` and a sandbox configuration file.
Custom runner implementations implement the same session operations; evaluators
receive no manager or provider identity. There is no unrestricted runner profile
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
Hosts must collect only files appropriate for that provider. The supplied
OpenAI host reads its credentials and optional `AUTOGRADER_AI_MODEL`; standalone
AI evaluators do not create a provider or retry missing batch results.

API assessments require `server_execution`, a factory returning a
`ServerSession`: staging/setup precede `start_server()` and `wait_ready()`, HTTP
requests use `make_request()`, and `close()` owns teardown even after startup or
readiness failure, including `stop_server()`. The host selects server startup configuration and readiness
policy. Current Docker pools disable network and provide no server lifecycle;
therefore their API outcomes fail with `SERVER_CAPABILITY_UNAVAILABLE` before
acquisition or scoring. Ordinary I/O pools do not gain network access. A host
that supports API assessment must supply the complete server profile explicitly.

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
| #312 remove PreFlightStep | Superseded: its remaining responsibility is the short, typed preparation sequence; legacy parsing/provider construction are removed. |
