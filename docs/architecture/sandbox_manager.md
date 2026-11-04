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

1. The host constructs `SandboxManager(pool_configs, client=None)` — for example
   `DockerHost` on first acquisition, or the control API lifespan.
2. Containers of provably dead owners on this host are reclaimed
   (`sandbox_manager.ownership.reclaim_dead_owners`). Other owners are untouched.
3. A `LanguagePool` is created per configured language and replenishes
   `pool_size` idle containers.
4. The monitor thread starts. No signal handlers or `atexit` hooks are installed;
   the host calls `shutdown()`.

### Request flow

```
manager.get_sandbox(Language.PYTHON)
    ↓
LanguagePool.acquire()
    ├── Idle sandbox available? → activate, return
    ├── tracked (idle+active+closing+quarantined) < scale_limit? → create, return
    └── otherwise → SandboxUnavailableError (a ValueError)
    ↓
SandboxContainer: prepare_workdir / inject_assets / run_command / run_commands / extract_file
    ↓
manager.dispose(sandbox) → LanguagePool.dispose()
    ├── mark closing; container.remove(force=True, v=True) outside the lock
    ├── removed or NotFound → disposed, forgotten
    └── Docker error → quarantined (tracked, counted, retried by the monitor)
```

A used sandbox is never reused. Replenishment is asynchronous (monitor thread),
so `dispose` returns as soon as Docker confirms removal.

### Shutdown

1. The host calls `shutdown()` (lifespan, `finally`, or `with SandboxManager(...)`).
2. The monitor thread is stopped and joined; pools refuse new acquisitions.
3. Every tracked container is disposed; quarantined ones get a final attempt.
4. Containers that still cannot be removed are logged and keep their owner
   labels, so the next manager on this host reclaims them.

---

## Configuration

Configuration is loaded from `sandbox_config.yml` at the project root:

```yaml
general:
    # Minimum idle sandboxes per language (always kept warm)
    pool_size: 3

    # Maximum total sandboxes (active + idle) per language
    scale_limit: 10

    # Seconds before destroying idle sandboxes above pool_size
    idle_timeout: 600

    # Maximum seconds a sandbox can be actively processing
    running_timeout: 120

    # Removal attempts for a quarantined container before it stays
    # quarantined for an operator (default 5)
    disposal_attempts: 5
```

### Sizing Guidelines

| Environment | `pool_size` | `scale_limit` | `idle_timeout` | `running_timeout` |
|-------------|-------------|---------------|----------------|-------------------|
| Development | 2–3 | 5–10 | 300 | 60 |
| Production (light) | 3–5 | 10 | 600 | 120 |
| Production (heavy) | 5–10 | 50+ | 600 | 120 |

> **Resource usage:** Each sandbox uses ~128 MB RAM + 0.5 CPU.

---

## Scaling Behavior

The pool scales between `pool_size` (minimum) and `scale_limit` (maximum):

```
                    pool_size              scale_limit
                       │                      │
   ┌───────────────────┼──────────────────────┼──────┐
   │  Always warm      │  Scale on demand     │ Hard │
   │  (idle containers)│  (created when busy) │ limit│
   └───────────────────┼──────────────────────┼──────┘
```

- **Below `pool_size`:** Pool automatically replenishes idle containers
- **Between `pool_size` and `scale_limit`:** New containers created on-demand when all are busy
- **At `scale_limit`:** Requests fail with an error (bottleneck)
- **Scale down:** Idle containers above `pool_size` are disposed once older than `idle_timeout`
- **Quarantine:** Containers whose removal failed still count toward `scale_limit`

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

### `run_command(command, timeout=30, workdir="/app")`
Executes a single shell command in the container. Returns a `CommandResponse`.

```python
result = sandbox.run_command("python main.py")
# result.stdout, result.stderr, result.exit_code, result.execution_time, result.category
```

### `run_commands(commands, program_command=None, timeout=30)`
Executes a program with stdin input streaming. Each item in `commands` is sent as a line to stdin.

```python
result = sandbox.run_commands(["5", "3"], program_command="python calculator.py")
# Sends "5\n3" to stdin of "python calculator.py"
```

### `extract_file(path, max_bytes=1_048_576)`
Reads one file from the container. Raises `FileNotFoundError` when it is missing.

---

## Models

### `Language` Enum

| Value | Docker Image |
|-------|-------------|
| `PYTHON` | `sandbox-py:latest` |
| `JAVA` | `sandbox-java:latest` |
| `NODE` | `sandbox-node:latest` |
| `CPP` | `sandbox-cpp:latest` |
| `C` | `sandbox-cpp:latest` (shares C++ image) |

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

### `ResponseCategory` Enum

| Value | Description |
|-------|-------------|
| `SUCCESS` | Program exited with code 0 |
| `RUNTIME_ERROR` | Program crashed (exception, segfault) |
| `COMPILATION_ERROR` | Compilation failed (Java/C++) |
| `TIMEOUT` | Execution exceeded time limit |
| `SYSTEM_ERROR` | Infrastructure failure (Docker error) |

### `CommandResponse` Dataclass

```python
@dataclass
class CommandResponse:
    stdout: str               # Standard output
    stderr: str               # Standard error
    exit_code: int            # Process exit code
    execution_time: float     # Execution time in seconds
    category: ResponseCategory  # Classified result
```

---

## Docker Images

Sandbox images are located in `sandbox_manager/images/`:

| File | Language | Base |
|------|----------|------|
| `Dockerfile.python` | Python | Python runtime |
| `Dockerfile.java` | Java | JDK |
| `Dockerfile.javascript` | Node.js | Node runtime |
| `Dockerfile.cpp` | C/C++ | GCC toolchain |

Build all images:
```bash
make sandbox-build-all
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
from sandbox_manager.models.pool_config import SandboxPoolConfig

manager = SandboxManager(SandboxPoolConfig.load_from_yaml("sandbox_config.yml"))
try:
    with manager.acquire_sandbox(Language.PYTHON) as sandbox:
        sandbox.prepare_workdir(files)
        result = sandbox.run_command("python main.py")
    # Disposed on exit, even on exception or timeout.
finally:
    manager.shutdown()
```

### Explicit dispose

```python
sandbox = manager.get_sandbox(Language.PYTHON)
try:
    result = sandbox.run_command("python main.py", timeout=30)
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
#   "python": { "idle": 2, "active": 1, "closing": 0, "quarantined": 0, "quarantine": [],
#               "total": 3, "pool_size": 3, "scale_limit": 10, "utilization": 33.3 },
#   "java":   { "idle": 3, "active": 0, "total": 3, "pool_size": 3, "scale_limit": 10, "utilization": 0.0 },
#   ...
# }
```

The monitor thread logs quarantined containers at error level every ~10 s and a
`HIGH LOAD` warning at ≥90% utilization. The control API exposes the same data
at `GET /stats` (token required).
