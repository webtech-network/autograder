# Sandbox Manager

The Sandbox Manager provides secure, isolated Docker container environments for executing student code. It manages container pools per language with automatic scaling, TTL-based lifecycle management, and graceful shutdown.

---

## Architecture

```
Host (DockerHost / control API lifespan / test)
└── SandboxManager            owns: OwnerLease, pools, monitor thread
    ├── LanguagePool (Python) idle → active → closing records
    ├── LanguagePool (Java)
    ├── LanguagePool (Node.js)
    └── LanguagePool (C++)
DockerSession                 one lease: acquire → prepare/use → dispose
```

Each `LanguagePool` manages the Docker containers for one language. Containers
are prestarted ("warm") and kept alive with `sleep infinity`, so commands can
run immediately through `docker exec`. Ownership, cleanup guarantees, dead-owner
reclamation and the private control API are specified in
[Sandbox ownership and the control API](../contracts/SANDBOX.md).

---

## Lifecycle

### Startup (host-owned)

1. The host constructs `SandboxManager(pool_configs, lease_dir=...)` and calls `start()`. `DockerHost` does this on first acquisition, and the control API does it in its lifespan.
2. The manager locks its owner lease file and reclaims containers whose owner is provably dead. Live owners and unverifiable owners are never touched.
3. The Docker runtime (`runsc`/`runc`) is resolved once from the runtime profile.
4. Each pool creates `pool_size` warm containers, and the monitor thread starts.

The library installs no signal handlers or `atexit` hooks.

### Request flow

```
session = DockerSession(manager, Language.PYTHON)   # manager.acquire()
    ├── idle sandbox available? → lease it
    ├── below scale_limit?      → create one and lease it
    └── otherwise               → SandboxCapacityError
session.prepare_workdir(files) / stage_fixture(...) / run_command(...) / read_artifact(...)
session.close()                                      # manager.dispose(): destroy, confirm, replenish
```

Used containers are always destroyed, never returned to the pool.

### Monitor (every second)

Each pass retries unconfirmed cleanup that is due, destroys leases older than
`running_timeout`, scales idle containers above `pool_size` down after
`idle_timeout`, and replenishes to `pool_size`.

### Shutdown

The host calls `shutdown()`. The monitor stops, and every idle, leased and
retained container is destroyed. Untracked containers carrying this owner's
label are swept. The lease file is removed only when everything is confirmed;
otherwise the next start reclaims the remainder, and `SandboxCleanupError` is
raised.

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

    # Maximum lease duration (acquisition to disposal), in seconds
    running_timeout: 120

runtimes:           # host runtime profiles: language identifier -> sandbox image
    python: sandbox-py:latest
    java: sandbox-java:latest
    node: sandbox-node:latest
    cpp: sandbox-cpp:latest
    c: sandbox-cpp:latest

runtime:            # the single Docker runtime/limit profile (see the ownership contract)
    runtime: auto   # auto | runsc | runc
    memory: 128m
    cpus: 0.5
    pids_limit: 64
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
- **Scale down:** Idle containers above `pool_size` are destroyed after `idle_timeout`
- **Unconfirmed cleanup** keeps counting against `scale_limit` until Docker confirms removal

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

### `make_request(method, endpoint, data=None, json_data=None, headers=None, timeout=5)`
Makes an HTTP request to a web application running inside the container. Used by the API Testing template.

```python
response = sandbox.make_request("GET", "/api/health")
# response.status_code, response.json(), response.text
```

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
| `IDLE` | Waiting in pool for a request |
| `BUSY` | Leased to one session |
| `CLOSING` | Disposal started; the record is retained until Docker confirms removal |
| `STOPPED` | Removal confirmed |

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
make build-sandboxes
```

### Container Security

Each container is created from `SandboxRuntimeProfile` (the single owner of these options):

- **Name:** Deterministic format `ag-sbx-{lang}-{owner8}-{seq4}` (e.g., `ag-sbx-python-a1b2c3d4-0001`)
- **Labels:** `autograder.sandbox.app`, `autograder.sandbox.owner` (owner ID), language, pool ID, creation time
- **Memory limit:** 128 MB (no swap)
- **CPU limit:** 0.5 CPU cores
- **Process limit:** 64 PIDs
- **Network:** Disabled (`network_mode="none"`)
- **Capabilities:** All dropped (`cap_drop=["ALL"]`)
- **File size limit:** 10 MB
- **Filesystem:** tmpfs `/app` 64 MB (exec) and `/tmp` 32 MB (noexec) on every runtime
- **Runtime:** `auto` uses gVisor (`runsc`) when Docker registers it and `runc` otherwise. The runtime is the only difference between them.
- **User:** Runs as non-root `sandbox` user

---

## Usage

```python
from execution_host.docker import DockerSession

with SandboxManager(pool_configs) as manager:          # host owns start/shutdown
    with DockerSession(manager, Language.PYTHON) as session:
        session.prepare_workdir(files)
        result = session.run_command("python main.py", timeout=30)
    # the sandbox is destroyed even if the block raised
```

A timeout or fatal error needs no special path: closing the session always
destroys the container.

---

## Monitoring

Get pool statistics:

```python
stats = manager.get_pool_stats()
# {
#   "python": { "idle": 2, "active": 1, "cleanup_pending": 0, "total": 3, "pool_size": 3,
#               "scale_limit": 10, "utilization": 33.3 },
#   "java":   { "idle": 3, "active": 0, "total": 3, "pool_size": 3, "scale_limit": 10, "utilization": 0.0 },
#   ...
# }
```

`manager.cleanup_problems()` lists retained cleanup records with attempts and the
last Docker error. The control API returns both at `GET /stats`.
