# Sandbox ownership and private control API

This contract covers the local Docker pools (`sandbox_manager.manager`,
`language_pool`), the private control API (`sandbox_manager.api`) and its client
(`sandbox_manager.remote_client`). The engine-facing session contract is in
[CAPABILITIES.md](CAPABILITIES.md); this page only describes what a host's
Docker execution profile guarantees behind `ExecutionSession.close()`.

## One owner from acquisition to confirmed disposal

A used sandbox is always destroyed; it is never returned to a pool. Each
sandbox moves through one lifecycle:

```text
idle -> active -> closing -> disposed
                          \-> quarantined -> (bounded retry) -> disposed
```

* `SandboxManager.get_sandbox(language)` hands one active sandbox to one caller.
* `SandboxManager.dispose(sandbox)` (and `LanguagePool.dispose`) is the only
  disposal path. It marks the sandbox `closing`, calls
  `container.remove(force=True, v=True)` outside the pool lock, and forgets the
  sandbox only after Docker confirms removal (`NotFound` counts as confirmed).
* Repeated disposal is safe and returns a `DisposalStatus`: `disposed`,
  `already_disposed`, `closing` (another caller is disposing it) or
  `quarantined`. Only a sandbox the pool never tracked raises `ValueError`.
* When Docker fails to remove a container, the sandbox is **quarantined**: it
  stays tracked, still counts against `scale_limit` (capacity is never silently
  over-committed), is logged at error level, and appears in
  `get_pool_stats()[language]["quarantine"]` with its attempts and last error.
  The pool monitor retries with exponential backoff (1 s doubling, 60 s cap) up
  to `disposal_attempts` (default 5, `general.disposal_attempts` in
  `sandbox_config.yml`). After exhaustion it stays quarantined and visible
  (`"exhausted": true`) for an operator. Shutdown makes one final attempt.
* Running-timeout and idle-timeout expiry use the same `dispose` path. A
  caller whose sandbox expired gets `already_disposed` from its own later
  cleanup.
* `DockerSession.close()` raises when disposal ends `quarantined`. The engine
  logs it, reports `CLEANUP_ERROR` to the optional observer, and keeps a
  completed grade completed; the pool keeps retrying.

There is one Docker profile (`sandbox_manager/docker_profile.py`): limits,
tmpfs mounts, `network_mode="none"`, `cap_drop=["ALL"]`, ulimits and labels are
declared once. gVisor (`runsc`) is preferred; when the daemon lacks it, the
same options are used without the `runtime` argument. That is the only allowed
difference. Previously the default-runtime path omitted the `/app` tmpfs because
runc mounts tmpfs `root:root 0755`, which the unprivileged `sandbox` user cannot
write; `/app` then fell back to an anonymous, unbounded image volume that was
leaked on removal. `/app` is now `rw,size=64m,exec,mode=1777` under both
runtimes, and removal passes `v=True`.

The image is not part of the profile or of the language: the `runtimes:` map
of `sandbox_config.yml` is the host's only language-to-image table
(`SandboxPoolConfig.image`). A pool exists only for listed languages; acquiring
another language raises `RuntimeUnavailableError` (see [LANGUAGES.md](LANGUAGES.md)).

## Host-owned lifetime and signals

Library code installs no signal handlers and no `atexit` hooks. The host that
constructs a `SandboxManager` (or `DockerHost`) owns it and calls `shutdown()`:

| Host | Where shutdown happens |
| --- | --- |
| Web API | `WebHost.close()` from the application lifespan (`DockerHost.close`) |
| Sandbox control API | its FastAPI lifespan `finally` (reaper stopped first) |
| GitHub Action | `GithubActionService.run_autograder` `finally`; `main` turns `SIGTERM` into `SystemExit` so the `finally` runs |
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
`sandbox-manager` service the fixed hostname `autograder-sandbox-manager`, so a
restarted container reclaims its predecessor's containers. Never run two
managers with the same hostname in different PID namespaces.

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

Handles are random (`secrets.token_urlsafe(32)`), never container ids. They are
bounded (`SANDBOX_MAX_HANDLES`, default the sum of pool `scale_limit`s; excess
acquisitions get 429 `HANDLE_LIMIT`) and expire after
`SANDBOX_HANDLE_TTL_SECONDS` (default 600) without use. A reaper thread disposes
expired handles and handles whose sandbox the pool already disposed (running
timeout); handles with an operation in flight are never reaped.

| Route | Purpose |
| --- | --- |
| `POST /sandboxes/{language}` `{"request_id"}` | acquire; replay-safe |
| `POST /sandboxes/{id}/prepare` | stage submission files in `/app` |
| `POST /sandboxes/{id}/inject` | stage base64 fixtures under `/tmp` |
| `POST /sandboxes/{id}/process` | run one process ([PROCESSES.md](PROCESSES.md)); never replayed |
| `GET /sandboxes/{id}/files?path=` | read one artifact |
| `DELETE /sandboxes/{id}` | dispose |
| `GET /stats` | pool stats (including quarantine) and handle counts |
| `GET /health` | unauthenticated liveness |

Errors use `{"detail": {"code", "message"}}` and never echo request input:

| Condition | Status | Code | Client exception |
| --- | ---: | --- | --- |
| Missing/invalid token | 401 | `UNAUTHORIZED` | `RemoteSandboxError` |
| Handle never issued or forgotten | 404 | `HANDLE_NOT_FOUND` | `SandboxHandleNotFound` |
| Artifact missing (valid handle) | 404 | `ARTIFACT_NOT_FOUND` | `ArtifactNotFound` (a `FileNotFoundError`) |
| Artifact too large / invalid path | 422 | `ARTIFACT_INVALID` | `ValueError` |
| Handle closed / closing | 410 | `HANDLE_CLOSED` | `SandboxHandleGone` |
| Handle expired or sandbox timed out | 410 | `HANDLE_EXPIRED` | `SandboxHandleGone` |
| Request id reused for another language | 409 | `REQUEST_ID_CONFLICT` | `RemoteSandboxError` |
| Too many handles / no sandbox | 429 / 503 | `HANDLE_LIMIT` / `SANDBOX_UNAVAILABLE` | `SandboxUnavailable` |
| No runtime profile for a valid language (absent from `runtimes:`) | 501 | `RUNTIME_UNAVAILABLE` | `RuntimeUnavailableError` (same as the local manager) |
| Unknown language identifier | 422 | `INVALID_REQUEST` | `RemoteSandboxError` |
| Execution infrastructure failure | 500 | `SANDBOX_ERROR` | `RemoteSandboxError` |
| Sandbox invalidated (termination or readback not confirmed) | 409 | `SANDBOX_INVALIDATED` | `SandboxInvalidatedError` (same as the local sandbox) |
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
| Client gives up or crashes after acquiring | The handle expires after the TTL; the reaper disposes it. |
| Acquire replayed after the handle closed | 410, no new container. |
| `DELETE` response lost | `DELETE` is idempotent: the handle is marked `closing`, disposed, then forgotten into a tombstone (1 hour, at most 10 000 entries), so a retried `DELETE` returns `already_disposed`. The client retries transport failures (3 attempts). |
| Disposal raises | The handle stays `closing` (500 `DISPOSAL_FAILED`); a repeated `DELETE` or the reaper retries. |
| Docker cannot remove the container | `DELETE` returns `quarantined`; the pool owns the retry record and reports it. |
| `/process` response lost | Never replayed automatically: the outcome is unknown and the caller gets `RemoteSandboxError` (`TRANSPORT_ERROR`), never a process result. |
| Control service restarts | Handles are lost (later calls get `HANDLE_NOT_FOUND`); the restarted manager reclaims the previous process's containers through its owner lease. |

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
| Process `stdin` | 1 MiB (base64 on the wire) | staged in chunks, not as one argument |
| Process `timeout` | (0, 600] s and at most the pool's `running_timeout` | client read deadline is timeout + 15 s |
| Process output | `max_output_bytes` per stream, 1 B–8 MiB (default 1 MiB), with `stdout_truncated`/`stderr_truncated` | bounded where the process runs, never after transfer |
| Artifact read | 1 MiB | same as local `extract_file` default |
| Request body | 48 MiB | base64 fixtures plus framing |

Client transport deadlines: connect 5 s; acquire 90 s (may start a container);
file/fixture transfer and artifact reads 120 s; dispose 60 s. Docker calls on the
server have no hard deadline beyond docker-py's own client timeout.

## Migration

* **Process route (ARC-08).** `POST /sandboxes/{id}/run` and `/run-batch`
  are replaced by `POST /sandboxes/{id}/process`, whose body and response are
  the shared process contract (`ProcessRequestModel`/`ProcessResultModel`, see
  [PROCESSES.md](PROCESSES.md)). Clients of the old routes must upgrade
  together with the control service.
* **New required setting.** Set `SANDBOX_API_TOKEN` (a long random secret, for
  example `python -c "import secrets; print(secrets.token_urlsafe(32))"`) for the
  control service and every remote client (`web` settings and the GitHub Action
  environment). Compose fails fast when it is unset. Local development may set
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
