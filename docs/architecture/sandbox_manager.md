# Sandbox Manager

The Sandbox Manager provides secure, isolated Docker container environments for executing student code. It manages container pools per language with automatic scaling, TTL-based lifecycle management, and graceful shutdown.

---

## Architecture

```
SandboxManager (one owner lease: owner id + hostname + boot:pid:start)
├── LanguagePool (Python)
│   ├── idle_sandboxes: deque[SandboxContainer]
│   ├── active_sandboxes: set
│   ├── closing_sandboxes: set        (removal in progress)
│   └── quarantined_sandboxes: set    (removal failed, retried with backoff)
├── LanguagePool (Java, Node.js, C/C++ …)
└── Monitor thread (every 1 s: timeouts → quarantine retry → replenish)
```

Each `LanguagePool` manages Docker containers for one language. Containers are
pre-started ("warm") with `sleep infinity` and run commands through `docker exec`.
The lifecycle, ownership and control API guarantees are specified in
[Sandbox ownership and private control API](../contracts/SANDBOX.md); this page
describes the internals.

---

## Lifecycle

### Startup (host-owned)

1. The host constructs `SandboxManager(pool_configs, client=None, max_sandboxes=N)`
   (or `SandboxManager.from_config(SandboxHostConfig.load_from_yaml(path))`) — for
   example `DockerHost` on first acquisition, or the control API lifespan.
2. Containers of provably dead owners on this host are reclaimed
   (`sandbox_manager.ownership.reclaim_dead_owners`). Other owners are untouched.
3. A `LanguagePool` is created per configured language, all sharing one
   `SandboxBudget` of N slots, and warms up `pool_size` idle containers.
4. The monitor thread starts. No signal handlers or `atexit` hooks are installed;
   the host calls `shutdown()`.

### Request flow

```
manager.get_sandbox(Language.PYTHON, wait_seconds=600)
    ↓
LanguagePool.acquire(wait_seconds)
    ├── take a budget slot: FIFO across all languages; when all N are held wait,
    │   and raise SandboxCapacityTimeout once wait_seconds passes
    ├── idle sandbox available? → activate, return
    └── otherwise create one outside the lock → activate, return
        (failure releases the slot: SandboxUnavailableError)
    ↓
SandboxContainer: prepare_workdir / inject_assets / run_process / extract_file
    ↓
manager.dispose(sandbox) → LanguagePool.dispose()
    ├── mark closing; container.remove(force=True, v=True) outside the lock
    ├── removed or NotFound → disposed, forgotten
    └── Docker error → quarantined (tracked, keeps its slot, retried by the monitor)
```

The slot is returned only when Docker confirms removal, so at every instant
creating + active + closing + quarantined ≤ N.

A used sandbox is never reused. Replenishment is asynchronous (monitor thread),
so `dispose` returns as soon as Docker confirms removal.

### Shutdown

1. The host calls `shutdown()` (lifespan, `finally`, or `with SandboxManager(...)`).
2. The monitor thread is stopped and joined; pools refuse new acquisitions and
   waiting acquisitions fail with `SandboxUnavailableError`.
3. Every tracked container is disposed, a container still being created is
   removed once Docker returns it, and quarantined ones get a final attempt.
4. Containers that still cannot be removed are logged and keep their owner
   labels, so the next manager on this host reclaims them.

---

## Configuration

Configuration is loaded from `sandbox_config.yml` at the project root:

```yaml
general:
    # The host sandbox budget N (required): creating + active + closing +
    # quarantined sandboxes of every language never exceed it
    max_sandboxes: 8

    # Warm idle containers per language, outside N (at most max_sandboxes)
    pool_size: 1

    # Maximum seconds a handed-out sandbox may live, counted from the grant
    running_timeout: 120

    # Removal attempts for a quarantined container before it stays
    # quarantined for an operator (default 5)
    disposal_attempts: 5

runtimes:           # host runtime profiles: language identifier -> sandbox image
    python: ghcr.io/webtech-network/autograder-sandbox-python:<tag>
    java: ghcr.io/webtech-network/autograder-sandbox-java:<tag>
    node: ghcr.io/webtech-network/autograder-sandbox-node:<tag>
    cpp: ghcr.io/webtech-network/autograder-sandbox-cpp:<tag>
    c: ghcr.io/webtech-network/autograder-sandbox-cpp:<tag>
```

A language missing from `runtimes:` has no pool; acquiring it raises
`RuntimeUnavailableError` (control API `501 RUNTIME_UNAVAILABLE`). Unknown keys,
the removed `scale_limit`/`idle_timeout`, a missing or non-positive
`max_sandboxes` and `pool_size > max_sandboxes` are rejected at startup.

---

## Capacity

- **Budget:** one host-wide number N bounds creating, active, closing and
  quarantined sandboxes across every language, for grading and deliberate
  execution alike. Size it by CPU, not by worker count: see the sizing rule in
  [JOBS.md](../contracts/JOBS.md#sandbox-capacity).
- **Saturation waits:** an acquisition beyond N waits in arrival order for a
  slot. Grading waits up to 600 s (`GRADING_CAPACITY_WAIT_SECONDS`), deliberate
  execution 10 s; expiry raises `SandboxCapacityTimeout`.
- **Warm pool:** `pool_size` idle containers per language hold no slot; taking
  one takes a slot. Warm-up only uses a slot no acquisition is waiting for. Used
  containers are never returned, so idle containers never exceed `pool_size`.
- **Creation and removal** run outside the lock, so N cold acquisitions take
  about one creation time instead of N.
- **Quarantine:** a container whose removal failed keeps its slot.

---

## SandboxContainer API

### `prepare_workdir(submission_files)`
Copies submission files into the container's `/app` directory. Supports nested directory structures (e.g., `services/service.java` → `/app/services/service.java`).

```python
sandbox.prepare_workdir(submission_files)
# Files are now available in /app inside the container
```

### `inject_assets(resolved_assets)`
Injects static assets (datasets, fixtures) into the container's `/tmp` directory using a shell-escaped Base64 `exec_run` write path compatible with gVisor.

```python
sandbox.inject_assets(resolved_assets)
# Assets are now available in /tmp (or specified path)
```

### `run_process(request)`
The only process operation (see [the process contract](../contracts/PROCESSES.md)).
`request` is a `ProcessRequest` with an exact `argv` (or an explicit `shell`
script), exact `stdin` bytes, `cwd`, a `timeout` and a per-stream output bound.
It returns a `ProcessResult` (`exited`, `timed_out` or `not_started`) and raises
for infrastructure failures.

```python
from autograder.models.process import ProcessRequest, lines_to_stdin
result = sandbox.run_process(ProcessRequest.command("python3 calculator.py", stdin=lines_to_stdin(["5", "3"])))
# result.status, result.exit_code, result.stdout, result.stderr, result.duration
```

### `extract_file(path, max_bytes=1_048_576)`
Reads back a regular file. It raises `FileNotFoundError` only when the file is
missing, `ArtifactTooLargeError` above `max_bytes`, and `ArtifactReadError` when
an existing file cannot be read.

---

## Models

### Languages and images

The domain `Language` (`autograder/models/language.py`) carries no image. The
`runtimes:` map in `sandbox_config.yml` assigns each language its image (see
[LANGUAGES.md](../contracts/LANGUAGES.md)).

### `SandboxState` Enum

| Value | Description |
|-------|-------------|
| `IDLE` | Warm, waiting in the pool |
| `ACTIVE` | Handed to one caller; disposed after use |
| `CLOSING` | Removal in progress |
| `QUARANTINED` | Removal failed; tracked and retried |
| `DISPOSED` | Docker confirmed removal |

### `DisposalStatus` Enum

`dispose()` returns `DISPOSED`, `ALREADY_DISPOSED`, `CLOSING` or `QUARANTINED`.

### Process results

`ProcessResult`, `ProcessStatus` and the deliberate-execution `ResponseCategory`
(`success`, `runtime_error`, `timeout`) live in `autograder/models/process.py`.
Classification uses the exit status only; see
[PROCESSES.md](../contracts/PROCESSES.md).

---

## Docker Images

Sandbox images are located in `sandbox_manager/images/`:

| File | Languages | Runtime |
|------|-----------|---------|
| `Dockerfile.python` | `python` | CPython 3.13 |
| `Dockerfile.java` | `java` | Temurin JDK 21 |
| `Dockerfile.node` | `node` | Node.js 24 |
| `Dockerfile.cpp` | `cpp`, `c` | GCC 15 |

Each image is published as a content-versioned reference that `sandbox_config.yml`
names; the manager refuses to start with a missing or mismatched image. See
[Runtime images](../contracts/LANGUAGES.md#runtime-images).

```bash
make sandbox-list        # language -> reference
make sandbox-build-all   # build this checkout's images under those references
```

### Container Security

Each container is created with:

- **Name:** Deterministic format `ag-sbx-{lang}-{pool8}-{seq4}` (e.g., `ag-sbx-py-a1b2c3d4-0001`)
  - `lang`: language key (`python`, `java`, `node`, `cpp`, `c`)
  - `pool8`: first 8 chars of the pool's UUID
  - `seq4`: zero-padded per-pool creation sequence
- **Memory limit:** 128 MB (no swap)
- **CPU limit:** 0.5 CPU cores
- **Process limit:** 64 PIDs
- **Network:** Disabled (`network_mode="none"`)
- **Capabilities:** All dropped (`cap_drop=["ALL"]`)
- **File size limit:** 10 MB
- **Filesystem:** tmpfs-based (`/app` 64 MB writable with mode 1777, `/tmp` 32 MB noexec) under both runtimes
- **Runtime:** gVisor (`runsc`) when available, falls back to default `runc`; the fallback only drops the `runtime` argument
- **Labels:** application label plus owner lease (see [ownership](../contracts/SANDBOX.md#owner-leases-and-orphan-reclamation))

All options are declared once in `sandbox_manager/docker_profile.py`.
- **User:** Runs as non-root `sandbox` user

---

## Usage Patterns

### Host-owned manager

```python
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxHostConfig

manager = SandboxManager.from_config(SandboxHostConfig.load_from_yaml("sandbox_config.yml"))
try:
    with manager.acquire_sandbox(Language.PYTHON) as sandbox:
        sandbox.prepare_workdir(files)
        result = sandbox.run_process(ProcessRequest.command("python main.py"))
    # Disposed on exit, even on exception or timeout.
    # A timed-out process and every process it started are killed before run_process returns.
finally:
    manager.shutdown()
```

### Explicit dispose

```python
sandbox = manager.get_sandbox(Language.PYTHON)
try:
    result = sandbox.run_process(ProcessRequest.command("python main.py", timeout=30))
finally:
    status = manager.dispose(sandbox)  # safe to repeat; QUARANTINED means retrying
```

Grading hosts normally use `execution_host.docker.DockerHost`, whose
`DockerSession.close()` disposes the sandbox and raises when removal is not
confirmed (the engine reports it as a cleanup error without changing the grade).

---

## Monitoring

Get pool statistics:

```python
stats = manager.get_pool_stats()
# {
#   "python": { "language": "python", "idle": 1, "creating": 0, "active": 1, "closing": 0,
#               "quarantined": 0, "quarantine": [], "total": 2, "pool_size": 1 },
#   ...
# }
manager.get_budget_stats()
# {"max_sandboxes": 8, "held": 1, "waiting": 0}
```

The monitor thread logs quarantined containers at error level every ~10 s. The
control API exposes the same data at `GET /stats` (`pools`, `budget`, `handles`;
token required).
