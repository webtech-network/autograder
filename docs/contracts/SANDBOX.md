# Sandbox ownership and the private control API

This contract covers sandbox lifecycle, ownership, cleanup and the private
control API (ARC-09 / INT-15). Process semantics such as command execution,
stdin, timeouts and output classification are covered by ARC-08. The engine-facing
`ExecutionSession` contract is described in [CAPABILITIES.md](CAPABILITIES.md).

## One lease from acquisition to disposal

Local `SandboxManager` and `RemoteSandboxManager` expose the same lease API:

```python
sandbox = manager.acquire(Language.PYTHON)  # the caller now owns this sandbox
sandbox.prepare_workdir(files)              # preparation and use
manager.dispose(sandbox)                    # Disposal.DISPOSED | Disposal.ALREADY_DISPOSED
```

`execution_host.docker.DockerSession` is the only lease object used by hosts. Its
constructor acquires the sandbox. Staging, fixtures, commands and artifact reads
go through the session, and `close()` disposes the sandbox. The session borrows
its manager. The host (`DockerHost`, the control API process or a test) owns the
manager and its lifetime. Sessions never shut managers down, and managers never
close sessions on a host's behalf except at shutdown.

Every disposal destroys the container. A used container is never returned to a
pool, which keeps runs strictly isolated. The former `release_sandbox`/`destroy_sandbox` pair, the
`acquire_sandbox` context managers, `initialize_sandbox_manager`/`get_sandbox_manager`
globals and the `DELETE /sandboxes/{id}/destroy` route are removed.

Repeated cleanup has a defined result:

| Call | Result |
| --- | --- |
| `dispose` of a leased sandbox, Docker confirms removal | `DISPOSED` |
| `dispose` again, or after lease expiry already destroyed it | `ALREADY_DISPOSED` |
| `dispose` while Docker removal fails | raises `SandboxCleanupError`. The record is retained. |
| `dispose` of a sandbox this manager never leased | `ValueError` |
| `DockerSession.close()` after confirmation | no-op |
| `DockerSession.close()` after `SandboxCleanupError` | retries disposal |

## No record is dropped before removal is confirmed

A pool record moves `idle → active → closing → dropped`. It is dropped only
after Docker confirms removal (`remove(force=True, v=True)` succeeds or reports
the container missing). If removal fails, the record stays in `closing`.
The monitor retries it with capped exponential backoff (1 s to 60 s). The record
still counts against `scale_limit`, and it appears in
`get_pool_stats()[lang]["cleanup_pending"]` and `cleanup_problems()` (attempts,
last error). Errors are logged at `ERROR`.

The engine treats `SandboxCleanupError` like any cleanup error. It logs the error,
reports `CLEANUP_ERROR` to the observer and preserves a completed grade. The host
still owns the retained record and recovers it.

Leases are bounded by `running_timeout`, the maximum lease duration. The monitor
destroys an abandoned lease, for example after a crashed client or a host bug.
A later `dispose` then returns `ALREADY_DISPOSED`, and remote operations on that
lease return `sandbox_expired`.

## Host ownership and dead-owner reclamation

`SandboxManager.start()` takes an exclusive `flock` on
`$SANDBOX_LEASE_DIR/<owner_id>.lease` and labels every container
`autograder.sandbox.owner=<owner_id>`. The kernel releases the lock when the
process exits for any reason, including `SIGKILL`. At startup a host reclaims
another owner's containers only after it acquires that owner's lock, which is
the proof of death.

* A live owner holds its lock. Its containers are never touched, even when both hosts use the same application label.
* A dead owner's lock can be acquired. Its containers are removed and its lease file is deleted after every removal succeeds.
* An owner with no lease file in this directory cannot be proven dead. Its containers are left alone and counted as `unverifiable` in `reclaim_report`. This covers another machine, another lease directory, and containers created before ownership labels existed.

Hosts sharing one Docker daemon must share one `SANDBOX_LEASE_DIR` for dead-owner
recovery. The default is `<tmp>/autograder-sandbox-leases`. The control API image
uses `/var/lib/autograder/sandbox-leases`, which Compose keeps on a named volume
so a restarted manager reclaims its predecessor. Tests use a fresh lease
directory per process, so they can only reclaim owners they created.

`shutdown()` stops the monitor and destroys idle, leased and retained containers.
It also sweeps any container carrying its owner label that no record tracks, for
example one that Docker created but never started. If everything is confirmed,
it deletes the lease file. Otherwise it keeps the file, releases the lock so the
next host start reclaims the remainder, and raises `SandboxCleanupError`.
Shutdown is safe to repeat.

## Host startup, shutdown and signals

The library installs no signal handlers, `atexit` hooks or process globals.

* The control API process is run by uvicorn, which owns `SIGINT`/`SIGTERM`. Its lifespan starts the manager and, on shutdown, disposes open handles and then calls `manager.shutdown()`.
* The web API's `WebHost` owns a `DockerHost`. The first acquisition starts the manager, and `WebHost.close()` (the uvicorn lifespan) shuts it down after workers drain.
* The Actions entrypoint converts `SIGTERM` into `SystemExit`, so `GithubActionService.run_autograder`'s `finally` closes the host.

## Runtime and limits have one owner

`SandboxRuntimeProfile` (the `runtime:` section of `sandbox_config.yml`) is the
only source of Docker creation options:

| Option | Default |
| --- | --- |
| `runtime` | `auto`: `runsc` (gVisor) when Docker registers it, else `runc`. `runsc` makes gVisor mandatory, and `runc` always uses runc. |
| `memory` (memory and memory+swap) | `128m` |
| `cpus` | `0.5` |
| `pids_limit` | `64` |
| `file_size_bytes` (`RLIMIT_FSIZE`) | `10000000` |
| `/app` tmpfs (`exec`, mode 1777) | `64m` |
| `/tmp` tmpfs (`noexec`, mode 1777) | `32m` |
| network / capabilities | `none` / all dropped |

The runtime is resolved once at startup from `docker info`, not by parsing
creation errors. The isolation kernel is the only permitted difference between
runtimes. Earlier runc fallbacks had no `/app` tmpfs, so every container leaked
an anonymous image volume; that difference is removed. `running_timeout` (lease
duration), `pool_size`, `scale_limit` and `idle_timeout` remain under `general:`.
The `runtimes:` map is the host's only language-to-image table; a pool exists
only for listed languages (see [LANGUAGES.md](LANGUAGES.md)).

## Private control API

### Deployment boundary

* **Private network only.** Compose does not publish port 8001. The service
  `expose`s it on the internal `sandbox-control` network, which only the API
  joins. `python -m sandbox_manager` binds `127.0.0.1` by default. Never put the
  service on a public interface or behind a public ingress.
* **One process, one worker, one replica.** Handles live in process memory. Do not
  run `--workers N`, multiple replicas, or a load balancer in front of it: another
  worker cannot see a handle, so requests would fail as `sandbox_not_found`. A
  distributed handle store is not required for this deployment and is
  deliberately not provided. Scale grading by `scale_limit` within the one
  process, or run separate private services with separate clients.
* **Authentication.** `SANDBOX_API_TOKEN` is required. The service refuses to
  start without it, and the client and `DockerHost(mode="remote")` refuse to
  connect without it. Every route except `GET /health` requires
  `Authorization: Bearer <token>`.
* **Lease ownership.** The client generates a random lease secret per
  acquisition and sends it as `X-Sandbox-Lease` on every request for that lease.
  The service stores only its SHA-256. A request whose secret does not match is
  treated exactly like an unknown handle, so a token holder cannot operate or
  dispose another execution. Handle IDs are random and are never container IDs.

### Routes and responses

| Route | Success | Distinct failures (`detail.code`) |
| --- | --- | --- |
| `POST /sandboxes/{language}` | 201 `{sandbox_id, language, lease_seconds}` | 503 `capacity_unavailable`, 501 `runtime_unavailable` (no `runtimes:` image for this language), 422 unknown identifier |
| `POST /sandboxes/{id}/prepare`, `/inject` | 200 | see below |
| `POST /sandboxes/{id}/run`, `/run-batch` | 200 command result | 422 `invalid_request` (timeout above lease) |
| `GET /sandboxes/{id}/files?path=&max_bytes=` | 200 file | 404 `artifact_not_found`, 413 `artifact_too_large` |
| `DELETE /sandboxes/{id}` | 200 `{"state":"disposed"}` | 202 `{"state":"closing"}` retained for retry |
| `GET /stats` | pools, handle counts, `cleanup_problems` | |
| `GET /health` | unauthenticated liveness | |

Every lease route can also return 401 `unauthorized`/`lease_required`, 404
`sandbox_not_found` (unknown or not owned), 410 `sandbox_expired` (closing,
disposed or expired by `running_timeout`), 413 `request_too_large`, and 500
`execution_failed` (infrastructure failure; details stay in server logs).

The client preserves these distinctions. `artifact_not_found` raises
`FileNotFoundError`, which the artifact evaluator scores as a missing student
file. `sandbox_not_found` and `sandbox_expired` raise `SandboxHandleError`.
Other failures raise `SandboxTransportError` with the code. All sandbox errors
are `RuntimeError`s, so the engine reports them as `SANDBOX_ERROR` or
`CAPABILITY_UNAVAILABLE`, never as a missing artifact or a zero.

### Limits and deadlines

| Limit | Value |
| --- | --- |
| Request body (`SANDBOX_MAX_BODY_BYTES`) | 64 MiB received bytes. This is above the 32 MiB HTTP submission limit after JSON/base64 expansion. |
| Command text | 64 KiB |
| Command `timeout` | 1–600 s and at most the pool's `running_timeout` |
| Artifact `max_bytes` | 1 B–8 MiB |
| Client transport deadline (`run`, `request`) | process timeout + 15 s |
| Client deadline: acquire / staging / dispose | 120 s / 120 s / 60 s |

Command output size is a process-semantics limit (ARC-08) and is not changed here.

### Recovery after loss

| Situation | Bounded recovery |
| --- | --- |
| Acquire response lost | The client retries once with the same lease secret, and the service returns the same handle (`acquire` is idempotent per secret). If the retry also fails, the lease expires after `running_timeout`. |
| Delete response lost | Disposal is idempotent. The client retries up to 3 times, and a recently closed handle answers 200 `disposed` from a bounded tombstone table (4096 entries). |
| Delete returns 202 | The service retains the record and retries. The client raises `SandboxCleanupError`, and a later `dispose` (or host shutdown) asks again. |
| Command, staging or HTTP request response lost | Never replayed automatically, because the outcome is uncertain. The client raises `SandboxTransportError`, and the session is then closed normally. |
| Client crashes or disconnects | The lease expires after `running_timeout`, and the monitor destroys it. |
| Service crashes | Its lease lock is released. The next start reclaims its containers (dead-owner proof), and clients see `sandbox_not_found`. |
| Service stops normally | The lifespan disposes every open handle and then shuts the manager down. |

Each lease owns one HTTP session. `dispose` closes it in `finally` on every path,
including delete failure. A retried `dispose` uses a fresh session and closes it too.

## Operational migration

* Set the same random `SANDBOX_API_TOKEN` on the control API and on every
  remote-mode host (web `SANDBOX_MODE=remote`, Actions `SANDBOX_MODE=remote`).
  Web startup rejects remote mode without it.
* Remove any published `8001` port mapping. Attach clients through a private network.
* Mount a persistent volume at `SANDBOX_LEASE_DIR` for the control API.
* Containers created by earlier versions have no owner label, and they are no
  longer reclaimed automatically. After stopping all old hosts and before
  starting upgraded ones, remove them once with `docker rm -f $(docker ps -aq --filter label=autograder.sandbox.app=autograder-sandbox)`.
  Old runc fallbacks also leaked anonymous volumes, which `docker volume prune`
  removes.
* Container labels now include `autograder.sandbox.owner`, and
  `autograder.sandbox.version` is `2.0`.
