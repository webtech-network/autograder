# Sandbox ownership and private control API

This contract covers the local Docker pools (`sandbox_manager.manager`,
`language_pool`), the private control API (`sandbox_manager.api`) and its client
(`sandbox_manager.remote_client`). The engine-facing session contract is in
[CAPABILITIES.md](CAPABILITIES.md); this page only describes what a host's
Docker execution profile guarantees behind `ExecutionSession.close()`.

The GitHub Action uses the same Docker profile but none of the pool, control
API or reclamation machinery described here: its `RunnerHost` creates one
sandbox of the selected language on the runner's Docker and removes it before
publication. Its isolation is stated separately, in
[Runner execution boundary](../github_action/trust.md#runner-execution-boundary).

## One owner from acquisition to confirmed disposal

A used sandbox is always destroyed; it is never returned to a pool. Each
sandbox moves through one lifecycle:

```text
idle -> active -> closing -> disposed
                          \-> quarantined -> (bounded retry) -> disposed
```

* `SandboxManager.get_sandbox(language, wait_seconds)` hands one active sandbox
  to one caller once it holds a slot of the host budget (below).
* `SandboxManager.dispose(sandbox)` (and `LanguagePool.dispose`) is the only
  disposal path. It marks the sandbox `closing`, calls
  `container.remove(force=True, v=True)` outside the pool lock, and forgets the
  sandbox only after Docker confirms removal (`NotFound` counts as confirmed).
* Repeated disposal is safe and returns a `DisposalStatus`: `disposed`,
  `already_disposed`, `closing` (another caller is disposing it) or
  `quarantined`. Only a sandbox the pool never tracked raises `ValueError`.
* When Docker fails to remove a container, the sandbox is **quarantined**: it
  stays tracked, keeps its budget slot (capacity is never silently
  over-committed), is logged at error level, and appears in
  `get_pool_stats()[language]["quarantine"]` with its attempts and last error.
  The pool monitor retries with exponential backoff (1 s doubling, 60 s cap) up
  to `disposal_attempts` (default 5, `general.disposal_attempts` in
  `sandbox_config.yml`). After exhaustion it stays quarantined and visible
  (`"exhausted": true`) for an operator. Shutdown makes one final attempt.
* Lifetime expiry uses the same `dispose` path: the monitor disposes an active
  sandbox past its own lifetime and an idle one too old to be granted. A
  caller whose sandbox expired gets `already_disposed` from its own later
  cleanup.
* `DockerSession.close()` raises when disposal ends `quarantined`. The engine
  logs it, reports `CLEANUP_ERROR` to the optional observer, and keeps a
  completed grade completed; the pool keeps retrying.

## One host-wide sandbox budget

A manager owns one budget of N slots, `general.max_sandboxes` in
`sandbox_config.yml` (required, at least 1). Every pool of the manager shares it,
so grading and deliberate execution of every language draw from the same N, in
local mode (the web process's manager) and remote mode (the control service's
manager) alike.

* A slot is taken before a container is created or an idle one is handed out,
  and returned only when Docker confirms the container's removal. At every
  instant **creating + active + closing + quarantined ≤ N**.
* When every slot is held, an acquisition **waits** in arrival order (one FIFO
  queue across languages) for up to its `wait_seconds`, then raises
  `SandboxCapacityTimeout`. Saturation never fails immediately unless the caller
  asked for no wait. Grading waits up to 600 s (`GRADING_CAPACITY_WAIT_SECONDS`,
  `execution_host/docker.py`) and reports expiry as a retryable
  `CAPABILITY_UNAVAILABLE`, never as an assessment; deliberate execution waits
  10 s and answers `503 EXECUTION_BUSY`. The sandbox's lifetime starts at the
  grant, never during the wait.
* Docker `create` and `remove` run outside the pool lock, so N cold acquisitions
  take about one creation time. A failed creation returns its slot and wakes the
  next waiter, and removes only its own uniquely named attempt.
* `pool_size` warm idle containers per language hold no slot (taking one takes a
  slot); warm-up only uses a slot no acquisition is waiting for. Used containers
  are never returned, so idle containers never exceed `pool_size`, which must not
  exceed N. Total containers are at most N + `pool_size` × languages.
* `shutdown()` wakes every waiter with `SandboxUnavailableError` and waits for
  in-flight creations, removing their containers before it returns.
* `get_budget_stats()` reports `max_sandboxes`, `held` and `waiting`.

## Sandbox lifetime

Every sandbox ends itself; neither its owner nor reclamation has to be alive.

* `get_sandbox(language, wait_seconds, lifetime_seconds)` grants a sandbox for
  `lifetime_seconds` from the grant (default: the host maximum). The host
  maximum is `general.running_timeout` in `sandbox_config.yml` (shipped and
  default: 900 s). The loader rejects a value below 92 s, the smallest session
  one execution needs (one 30 s process + 2 s + 60 s), and the web host refuses
  to start below 100 s, deliberate execution's fixed budget;
  a longer lifetime raises `SandboxLifetimeExceeded` before any wait, and the
  control API answers `422 LIFETIME_EXCEEDED`. Graders ask for the run's
  `budget.session_seconds` (see [CAPABILITIES.md](CAPABILITIES.md#execution-budget))
  and report a refusal as `EXECUTION_BUDGET_EXCEEDED`; hosts compare the same
  numbers before any acquisition.
* At the grant a root control exec (`docker_profile.LIFETIME`), which the
  submission cannot signal, sleeps for the lifetime and then kills every other
  process with `kill -KILL -1` (a shell builtin, so a submission at its pids
  limit cannot stop it). PID 1's child dies, PID 1 exits and the container
  stops with nothing running, under runsc and runc alike, whatever happened to
  its owner (crash, `SIGKILL`, a recreated container with another hostname).
* PID 1 itself runs `sleep <2 × running_timeout + 60>`: an idle container is
  granted only while younger than `running_timeout`, the monitor disposes older
  ones, and an orphaned idle container stops by itself at that bound (1860 s
  shipped). No submission code has run in an idle container: student processes
  only ever run in a granted one, which stops at its own lifetime.
* A run the lifetime ended is an infrastructure failure (`SANDBOX_ERROR`): the
  sandbox records the instant its lifetime passes (never later than the real
  stop), and any operation, control failure or readback after it invalidates the
  sandbox instead of reporting a process result.
* The pool's monitor disposes an active sandbox once its lifetime passed, and the
  control API's reaper then forgets its handle. After a crash, a stopped
  container's record remains until its owner lease is reclaimed (startup
  reclamation on the same hostname, or `python -m sandbox_manager.reclaim
  --dead-host <name>`). Reclamation still force-removes a dead owner's
  containers, running or not; it is no longer what ends a sandbox.

## Isolation profile and runtime

There is one Docker profile (`sandbox_manager/docker_profile.py`): limits,
tmpfs mounts, the read-only root filesystem, `network_mode="none"`, identities,
capabilities, ulimits and labels are declared once. PID 1 is Docker's init
(`init=True`, reaping orphans) running a bounded `sleep` (see
[Sandbox lifetime](#sandbox-lifetime)) as `root`; control execs that can run
beside the submission also run as `root`. `root` keeps only `KILL`
(to end every submission process) and `DAC_OVERRIDE` (to read back and remove
what the submission wrote, whatever its permissions); every other capability is
dropped. Submission processes run as the image's `sandbox` user with no
capabilities, under `no-new-privileges`, so they cannot signal PID 1 or a
control exec. The container holds nothing the submission may not see: its own
files, fixtures staged readable, and the image. Every image is built without
setuid/setgid files (see [Runtime images](LANGUAGES.md#runtime-images)).

**Storage.** The root filesystem is read-only, so no write reaches the
container's writable layer on host disk: its `SizeRw` stays 0 under both
runtimes, and the image's `VOLUME /app` never becomes an anonymous volume. A
submission can write these in-memory tmpfs mounts, each bounded by its size,
charged to the container's 128 MiB memory limit (no swap) and removed with the
container:

| Path | Bound | Use |
| --- | ---: | --- |
| `/app` | 64 MiB, `exec`, mode 1777 | the workspace: submission files, build outputs, artifacts |
| `/tmp` | 32 MiB, `noexec`, mode 1777 | fixtures, per-run stdin/output files, runtime scratch (JVM `hsperfdata`, compiler temporaries) |
| `/dev/shm` | 64 MiB, `noexec` | POSIX shared memory |

The sizes sum to 160 MiB, intentionally above the 128 MiB memory limit: each
mount stops at its own size, and together they stop at the memory limit, where
filling them ends the sandbox as `SandboxExhausted` (an assessed zero) under both
runtimes. Under runc, and not gVisor, `/dev/mqueue` (POSIX message queues) is
also writable; it holds no file bytes, only queues in kernel memory bounded per
user by `RLIMIT_MSGQUEUE` (819200 bytes). No other path is writable.

No single file exceeds 10 MB (`fsize`). Filling `/tmp` can only make the
submission's own output unreadable; filling memory ends the sandbox as
`SandboxExhausted` ([PROCESSES.md](PROCESSES.md)). The per-sandbox host-disk
bound is therefore **0 bytes**, and the memory-backed bound is the memory limit.

**Runtime.** The OCI runtime is one explicit host decision,
`general.runtime` in `sandbox_config.yml` (`runtime=` for
`SandboxManager`), with no default:

* `runsc`: gVisor is required. A `SandboxManager` refuses to start
  (`IsolationRuntimeError`) when the Docker daemon does not offer it, before it
  creates any container, and logs the decision at startup. Both long-running
  hosts build their manager when they start, before they report ready: the
  control service in its lifespan, and a local-mode HTTP API in its startup
  (`DockerHost.start`). Either one therefore exits at service start with
  `IsolationRuntimeError` (naming the runtimes the daemon offers) instead of
  serving and failing every execution grading. Check that `docker info` lists
  `runsc` before deploying, or deploy `runtime: runc` deliberately. The Action
  does not read `general.runtime`: its `RunnerHost` requests `runc` explicitly
  and builds its manager, with the same check, before grading only when the
  definition executes code.
* `runc`: accepted explicitly; submissions share the host kernel. The manager
  logs a warning at startup.

The runtime argument is the only difference between the two; every sandbox of
a host uses the configured one. A failed container start, including a
transient gVisor failure, fails only that acquisition
(`SandboxUnavailableError`, retryable, its budget slot returned and any
partially created container removed by its unique name). The next acquisition
uses the same runtime: there is no fallback.

### Environments and supported topology

The profile's limits are the same in every environment; the environments
differ in the runtime and in who can reach the Docker daemon.

| Environment | Runtime | Who holds the Docker socket | Exposure |
| --- | --- | --- | --- |
| HTTP API, remote mode (`SANDBOX_MODE=remote`) with the control service | `runsc` (the shipped `sandbox_config.yml`) | only the control service | **The supported internet-facing topology.** The API container has no Docker socket; the control service is private (below). |
| HTTP API, local mode (`SANDBOX_MODE=local`) | `runsc`; `runc` for development (a configuration copy via `SANDBOX_CONFIG_FILE`, see [the development guide](../guides/development.md#running-the-api-locally)) | the API process | Not supported internet-facing: a compromised API process owns the Docker host. Use it for development, tests and private single-host deployments. |
| GitHub Action | `runc` (hosted runners have no gVisor) | the Action on the runner VM | One run per runner VM; the runner VM is the outer boundary. Submitter, actor and token separation: [trust.md](../github_action/trust.md). |
| CI and local test suites | `runc` always, and `runsc` where installed | the test process | CI's isolation job installs the pinned gVisor release (`make gvisor-install`) and runs the per-runtime suites below under both (`make test-isolation`); the other Docker suites run under runc. CI's HTTP job also installs it, because `make test-http` runs the shipped images with their own `sandbox_config.yml` (`runsc`), exactly as deployed. |

The supported internet-facing deployment is the repository's
`docker-compose.yml` shape: the API in remote mode without the Docker socket,
one `sandbox-manager` service holding the socket on the internal network only,
and a daemon offering `runsc`. A deployment that mounts `/var/run/docker.sock`
into an internet-facing API (local mode) is not supported.

### Isolation guarantees

Each guarantee is pinned by a real-Docker test that runs under every runtime
the daemon offers (`runsc` when installed, `runc` always) unless noted. The
hostile-submission suite is `tests/integration/test_hostile_submissions.py`.

| Guarantee | Pinned by |
| --- | --- |
| Every sandbox uses the configured runtime and this one profile (read-only root, tmpfs, limits, capabilities, `no-new-privileges`) | `tests/integration/test_hostile_submissions.py::test_the_configured_runtime_and_the_one_profile_are_in_effect` |
| A disk-fill probe (fsync, page cache dropped) writes nothing outside the tmpfs mounts and grows no host storage (`SizeRw` 0, no volume, no log) | `tests/integration/test_hostile_submissions.py::test_disk_fill_never_reaches_host_storage` |
| Only the declared paths are writable (the tmpfs mounts, and `/dev/mqueue` under runc); no regular file is writable | `tests/integration/test_hostile_submissions.py::test_only_the_declared_paths_are_writable` |
| Each writable path stops at its size bound, in memory | `tests/integration/test_hostile_submissions.py::test_each_writable_path_is_bounded_in_memory_and_by_its_size` |
| The submission cannot write the container log | `tests/integration/test_hostile_submissions.py::test_writes_to_the_container_log_are_refused` |
| No network egress (loopback only, no DNS) | `tests/integration/test_hostile_submissions.py::test_no_network_egress` |
| No host environment, credentials or Docker socket are visible; PID 1's environment is unreadable | `tests/integration/test_hostile_submissions.py::test_no_host_credentials_environment_or_docker_socket` |
| No capabilities, `no-new-privileges`, no setuid/setgid path in the running sandbox | `tests/integration/test_hostile_submissions.py::test_no_privileges_capabilities_or_setuid_paths` |
| No built runtime image carries setuid/setgid files (runtime-independent) | `tests/integration/test_hostile_submissions.py::test_no_built_image_carries_setuid_or_setgid_files` |
| Signals to PID 1 and control processes are refused | `tests/integration/test_hostile_submissions.py::test_signals_to_control_processes_are_refused`, `tests/integration/test_sandbox_attribution.py::test_student_cannot_signal_the_control_processes` |
| No file or process of one submission reaches the next | `tests/integration/test_hostile_submissions.py::test_no_residue_reaches_the_next_submission` |
| The memory limit ends an exhausting submission (`SandboxExhausted`) | `tests/integration/test_hostile_submissions.py::test_memory_limit_ends_an_exhausting_submission` |
| Memory and process-count exhaustion are one assessed result, repeated 20 times per runtime | `tests/integration/test_sandbox_attribution.py::test_exhaustion_is_one_assessed_result_and_ends_the_sandbox` |
| Output is bounded where the process runs | `tests/integration/test_process_contract.py::test_output_is_bounded_by_the_executing_host` |
| Artifacts are bounded and a symbolic link is never an artifact | `tests/integration/test_outcome_size_docker.py::test_flooded_stderr_and_artifact_reports_are_bounded`, `tests/integration/test_sandbox_attribution.py::test_a_symbolic_link_is_no_artifact_under_either_runtime` |
| A transient gVisor start failure fails one acquisition and never downgrades (`runsc` only) | `tests/integration/test_hostile_submissions.py::test_a_transient_gvisor_failure_fails_one_acquisition_and_never_downgrades` |

`tests/unit/sandbox/test_isolation_contract.py` keeps this table and the suite
in step: every referenced test exists, and every test of the hostile suite is
referenced here.

The image is not part of the profile or of the language: the `runtimes:` map
of `sandbox_config.yml` is the host's only language-to-image table
(`SandboxPoolConfig.image`). A pool exists only for listed languages; acquiring
another language raises `RuntimeUnavailableError` (see [LANGUAGES.md](LANGUAGES.md)).
A manager starts only when every configured image is present locally and its
`autograder.runtime.languages` label declares the language; otherwise it raises
`RuntimeImageError` before reclaiming or creating any container, and never pulls
an image (see [Runtime images](LANGUAGES.md#runtime-images)).

## Host-owned lifetime and signals

Library code installs no signal handlers and no `atexit` hooks. The host that
constructs a `SandboxManager` (or `DockerHost`) owns it and calls `shutdown()`:

| Host | Where shutdown happens |
| --- | --- |
| Web API | `WebHost.close()` from the application lifespan (`DockerHost.close`) |
| Sandbox control API | its FastAPI lifespan `finally` (reaper stopped first) |
| GitHub Action | `RunnerHost.close()` from `GithubActionService.close()`, after grading and before publication; grading runs in a worker thread and `main` turns `SIGTERM` into `SystemExit` in the waiting main thread, so the `finally` runs without interrupting the sandbox bookkeeping |
| Tests | the integration `conftest.py` session finalizer |

`shutdown()` is idempotent: it stops and joins the monitor thread, refuses new
acquisitions, disposes every tracked container and logs any that remain
unconfirmed. A manager closes the Docker client only if it created it.

## Owner leases and orphan reclamation

Every container carries the application label and its owner lease:

| Label | Value |
| --- | --- |
| `autograder.sandbox.app` | `autograder-sandbox` |
| `autograder.sandbox.owner` | random id, one per manager instance |
| `autograder.sandbox.owner_host` | hostname of the owning process |
| `autograder.sandbox.owner_process` | `<boot_id>:<pid>:<process start ticks>` from `/proc` |

When a manager starts, it removes only containers whose owner is **provably
dead**: the owner ran on this hostname and either the boot id differs (the
kernel rebooted) or the pid is no longer running with the recorded start time.
Containers of another hostname, of a live process (including another manager
in the same process), without owner labels (the old label scheme), or where
`/proc` gives no answer (for example macOS hosts) are never touched
automatically.

The hostname must identify one PID namespace. Compose gives the single
`sandbox-manager` service the hostname `<project>-sandbox-manager`, stable across
restarts and unique per Compose project, so a restarted container reclaims its
predecessor's containers and never another stack's. Never run two managers with
the same hostname in different PID namespaces.

Operators reclaim what automation cannot prove dead with:

```bash
python -m sandbox_manager.reclaim                     # list containers, owners and status
python -m sandbox_manager.reclaim --dead              # what startup would reclaim
python -m sandbox_manager.reclaim --owner <owner-id>  # one dead owner lease
python -m sandbox_manager.reclaim --dead-host <name>  # a decommissioned host / old container hostname
python -m sandbox_manager.reclaim --legacy            # containers from before owner labels
python -m sandbox_manager.reclaim --legacy --dry-run  # print only
```

The command refuses containers whose owner is visibly alive on the machine it
runs on. Run it where the Docker daemon is reachable (in Compose:
`docker compose exec sandbox-manager python -m sandbox_manager.reclaim ...`).

## Staging

Submission files (`prepare_workdir`), a fixture set (`inject_assets`, which
receives a grading's whole set from one `ExecutionSession.stage_fixtures` call,
see [CAPABILITIES.md](CAPABILITIES.md)) and process stdin above 48 KiB are each
staged in **one transfer**: the host packs the files into a tar archive and
streams it to the stdin of a single `tar -x` exec, so a staging operation costs
the same three Docker calls (create, start, inspect the exec) for one file or
for the 100-file, 5 MiB submission and the 100-fixture, 32 MiB fixture maxima. Docker's archive upload cannot reach the `/app` and `/tmp`
tmpfs mounts, so the exec's stdin is the transport; the command is a fixed
argument vector and no caller value becomes shell text or an argument.

* Every path is normalized and checked before anything is sent: a submission
  path that is absolute or leaves `/app`, or a fixture target that leaves
  `/tmp`, rejects the whole operation and nothing is staged.
* Bytes are exact, empty files included. Submission files are `0644` and owned
  by `sandbox`; fixtures are owned by `root` (`0444` when read-only, else
  `0644`), so the submission cannot change either kind of fixture. Missing
  parent directories are created `0755` by the same user; existing directories,
  `/tmp` (`1777`) included, keep their mode.
* A transfer that does not complete cleanly (the archive could not be
  delivered or extracted, `/tmp` is full, the host stopped the container) may
  have staged part of the files, so it invalidates the sandbox and raises
  `ProcessExecutionError` (wrapped as `RuntimeError` by `prepare_workdir`, as
  before). A partial workdir is never reported as staged. Each transfer is
  bounded by the 60 s control deadline.

The runtime image provides `tar` (BusyBox or GNU) next to the `/bin/sh` tools
the control scripts already use. Ending the transfer half-closes the exec's
attach socket, which a TLS connection cannot do, so the sandbox host reaches the
Docker daemon over its unix socket (as every shipped deployment does) or plain
TCP; with a TLS `DOCKER_HOST` staging fails with `ProcessExecutionError` before
any exec is created.

## Private control API

The control API runs code on behalf of trusted hosts. Its deployment boundary
is a private network plus a shared bearer token:

* Every route except `GET /health` (liveness, no data) requires
  `Authorization: Bearer $SANDBOX_API_TOKEN`, compared in constant time.
* The service refuses to start without `SANDBOX_API_TOKEN` unless
  `SANDBOX_API_ALLOW_UNAUTHENTICATED=true` is set for local development; it then
  logs a loud warning.
* Compose exposes port 8001 only on the internal network (`expose`, no
  `ports`) and passes the token to both services. Never publish this port.

Handles are random (`secrets.token_urlsafe(32)`), never container ids. Each
holds one budget slot, so the budget bounds them. An acquisition carries
`wait_seconds` (0–900, default 0) and waits for a slot in a dedicated pool of
threads, never in the threadpool the other routes use, so waiting acquisitions
cannot starve the `DELETE` that frees a slot. Acquisitions run concurrently; a
replay of a request id that is still waiting returns the same handle when it is
granted. Handles expire after `SANDBOX_HANDLE_TTL_SECONDS` (default 600) without use. A reaper thread disposes
expired handles and handles whose sandbox the pool already disposed (running
timeout); handles with an operation in flight are never reaped.

| Route | Purpose |
| --- | --- |
| `POST /sandboxes/{language}` `{"request_id", "wait_seconds", "lifetime_seconds"}` | acquire, waiting for a budget slot, for a lifetime (default `running_timeout`); replay-safe |
| `POST /sandboxes/{id}/prepare` | stage submission files in `/app` |
| `POST /sandboxes/{id}/inject` | stage base64 fixtures under `/tmp` |
| `POST /sandboxes/{id}/process` | run one process ([PROCESSES.md](PROCESSES.md)); never replayed |
| `GET /sandboxes/{id}/files?path=` | read one artifact |
| `DELETE /sandboxes/{id}` | dispose |
| `GET /stats` | pool stats (including quarantine), budget and handle counts |
| `GET /health` | unauthenticated liveness |

Errors use `{"detail": {"code", "message"}}` and never echo request input:

| Condition | Status | Code | Client exception |
| --- | ---: | --- | --- |
| Missing/invalid token | 401 | `UNAUTHORIZED` | `RemoteSandboxError` |
| Handle never issued or forgotten | 404 | `HANDLE_NOT_FOUND` | `SandboxHandleNotFound` |
| Artifact missing (valid handle) | 404 | `ARTIFACT_NOT_FOUND` | `ArtifactNotFound` (a `FileNotFoundError`) |
| Artifact too large / invalid path | 422 | `ARTIFACT_INVALID` | `ValueError` |
| Handle closed / closing | 410 | `HANDLE_CLOSED` | `SandboxHandleGone` |
| Handle expired or sandbox reached its lifetime | 410 | `HANDLE_EXPIRED` | `SandboxHandleGone` |
| Request id reused for another language | 409 | `REQUEST_ID_CONFLICT` | `RemoteSandboxError` |
| No budget slot within `wait_seconds` | 503 | `CAPACITY_TIMEOUT` | `SandboxCapacityTimeout` (same as the local manager) |
| `lifetime_seconds` above the host's `running_timeout` | 422 | `LIFETIME_EXCEEDED` | `SandboxLifetimeExceeded` (same as the local manager) |
| Service shutting down, or container creation failed | 503 | `SANDBOX_UNAVAILABLE` | `SandboxUnavailable` |
| No runtime profile for a valid language (absent from `runtimes:`) | 501 | `RUNTIME_UNAVAILABLE` | `RuntimeUnavailableError` (same as the local manager) |
| Unknown language identifier | 422 | `INVALID_REQUEST` | `RemoteSandboxError` |
| Execution infrastructure failure | 500 | `SANDBOX_ERROR` | `RemoteSandboxError` |
| Sandbox invalidated by an earlier failure (termination or readback not confirmed, or the host stopped or removed it) | 409 | `SANDBOX_INVALIDATED` | `SandboxInvalidatedError` (same as the local sandbox) |
| The submission exhausted the sandbox's memory or process limit | 409 | `SANDBOX_EXHAUSTED` | `SandboxExhausted` (same as the local sandbox) |
| Artifact exists but readback failed | 500 | `ARTIFACT_READ_FAILED` | `ArtifactReadError` (same as the local sandbox) |
| Disposal raised unexpectedly | 500 | `DISPOSAL_FAILED` | `RemoteSandboxError` |
| Schema or limit violation | 422 | `INVALID_REQUEST` | `RemoteSandboxError` |
| Body too large | 413 | `REQUEST_TOO_LARGE` | `RemoteSandboxError` |

Only a valid handle can yield `ArtifactNotFound`, so an unknown sandbox never
looks like a missing `output.txt`. All other client exceptions are
`RuntimeError`s, which evaluators report as infrastructure failures.

### Response loss, crashes and expiry

| Situation | Bounded recovery |
| --- | --- |
| Acquire response lost | The client retries transport failures (3 attempts) with the same `request_id`; the service returns the same handle, never a second container. |
| Client gives up or crashes after acquiring | The sandbox stops itself at its lifetime; the handle expires after the TTL or the lifetime, and the reaper disposes it. |
| Acquire replayed after the handle closed | 410, no new container. |
| `DELETE` response lost | `DELETE` is idempotent: the handle is marked `closing`, disposed, then forgotten into a tombstone (1 hour, at most 10 000 entries), so a retried `DELETE` returns `already_disposed`. The client retries transport failures (3 attempts). |
| Disposal raises | The handle stays `closing` (500 `DISPOSAL_FAILED`); a repeated `DELETE` or the reaper retries. |
| Docker cannot remove the container | `DELETE` returns `quarantined`; the pool owns the retry record and reports it. |
| `/process` response lost | Never replayed automatically: the outcome is unknown and the caller gets `RemoteSandboxError` (`TRANSPORT_ERROR`), never a process result. |
| Control service restarts or is killed | Handles are lost (later calls get `HANDLE_NOT_FOUND`); every sandbox still stops itself at its lifetime, and the restarted manager removes the previous process's containers through its owner lease. |

The client closes each handle's HTTP session in `finally`, including when
deletion fails, and its HTTP adapter performs no automatic retries.

### Worker model

Handles live in the service's process memory. Run **exactly one worker
process** (`uvicorn --workers 1`, as in `Dockerfile.sandbox` and
`python -m sandbox_manager`); the service refuses to start when
`WEB_CONCURRENCY` is greater than 1. One service instance per Docker host and
hostname. Scaling out means separate services with separate tokens/URLs, not a
shared handle store. A distributed handle database is out of scope until a
deployment needs it.

### Limits

Wire limits agree with the operations they guard (`sandbox_manager/models/api_models.py`):

| Input/output | Limit | Reason |
| --- | --- | --- |
| Submission files | 100 files, 1 MiB each, 5 MiB total | shared `sandbox_manager.submission_contract` limits |
| Fixtures | 100, 32 MiB decoded total | `/tmp` tmpfs size |
| Process `argv` / `shell` text | 64 KiB | below the Linux 128 KiB per-argument limit |
| Process `stdin` | 1 MiB (base64 on the wire) | above 48 KiB staged in one transfer, not as an argument |
| Process `timeout` | (0, 600] s and at most the pool's `running_timeout` (a process past the sandbox's own lifetime is ended by it) | client read deadline is timeout + 15 s |
| Process output | `max_output_bytes` per stream, 1 B–8 MiB (default 1 MiB), with `stdout_truncated`/`stderr_truncated` | bounded where the process runs, never after transfer |
| Artifact read | 1 MiB | same as local `extract_file` default |
| Request body | 48 MiB | base64 fixtures plus framing |

Client transport deadlines: connect 5 s; acquire `wait_seconds` + 90 s (may start a container);
file/fixture transfer and artifact reads 120 s; dispose 60 s. Docker calls on the
server have no hard deadline beyond docker-py's own client timeout.

## Migration

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
  `stage_fixtures` session call ([CAPABILITIES.md](CAPABILITIES.md#migration));
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
