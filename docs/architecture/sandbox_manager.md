# Sandbox Manager

The Sandbox Manager provides secure, isolated Docker container environments for executing student code. It manages container pools per language with automatic scaling, TTL-based lifecycle management, and graceful shutdown.

---

## Architecture

```
SandboxManager
├── LanguagePool (Python)
│   ├── idle_sandboxes: deque[SandboxContainer]
│   └── active_sandboxes: set[SandboxContainer]
├── LanguagePool (Java)
│   ├── idle_sandboxes
│   └── active_sandboxes
├── LanguagePool (Node.js)
│   └── ...
├── LanguagePool (C++)
│   └── ...
└── Monitor Thread (checks TTLs + replenishes every 1s)
```

Each `LanguagePool` manages a set of Docker containers for one language. Containers are pre-started ("warm") and kept alive with `sleep infinity`, ready to execute commands instantly via `docker exec`.

---

## Lifecycle

### Startup

1. `initialize_sandbox_manager()` is called at application startup
2. Orphaned containers from previous runs are cleaned up (identified by `autograder.sandbox.app` label)
3. A `LanguagePool` is created for each configured language
4. Each pool calls `replenish()` to create `pool_size` idle containers
5. A background monitor thread starts (runs every 1 second)
6. Signal handlers (`SIGTERM`, `SIGINT`) and `atexit` hooks are registered for cleanup

### Request Flow

```
get_sandbox_manager()
    ↓
manager.get_sandbox(Language.PYTHON)
    ↓
LanguagePool.acquire()
    ├── Idle sandbox available? → Move to active, return
    ├── Below scale_limit? → Create new container on-demand, return
    └── At scale_limit, all busy? → Raise ValueError (bottleneck)
    ↓
SandboxContainer
    ├── prepare_workdir(submission_files)  → Copy files into /app
    ├── run_command("python main.py")     → Execute single command
    ├── run_commands(["input1", "input2"], program_command="python main.py")  → Execute with stdin
    └── make_request("GET", "/api/data")  → HTTP request to containerized app
    ↓
manager.release_sandbox(Language.PYTHON, sandbox)
    ↓
LanguagePool.release()
    ├── Below scale_limit? → Return to idle pool for reuse
    └── Above scale_limit? → Destroy container (scale down)
```

### Shutdown

1. `shutdown()` is called (via signal handler, atexit, or context manager)
2. Each pool destroys all containers (both active and idle)
3. Docker containers are stopped and removed

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
- **Scale down:** Containers released above `pool_size` are destroyed if they exceed `idle_timeout`

---

## SandboxContainer API

### `prepare_workdir(submission_files)`
Copies submission files into the container's `/app` directory. Supports nested directory structures (e.g., `services/service.java` → `/app/services/service.java`).

```python
sandbox.prepare_workdir(submission_files)
# Files are now available in /app inside the container
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
| `BUSY` | Currently executing a submission |
| `STOPPED` | Container has been stopped |

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

Each container is created with:

- **Memory limit:** 128 MB (no swap)
- **CPU limit:** 0.5 CPU cores
- **Process limit:** 64 PIDs
- **Network:** Disabled (`network_mode="none"`)
- **Capabilities:** All dropped (`cap_drop=["ALL"]`)
- **File size limit:** 10 MB
- **Filesystem:** tmpfs-based (`/app` 64 MB writable, `/tmp` 32 MB)
- **Runtime:** gVisor (`runsc`) when available, falls back to default `runc`
- **User:** Runs as non-root `sandbox` user

---

## Usage Patterns

### Direct Acquire/Release

```python
manager = get_sandbox_manager()
sandbox = manager.get_sandbox(Language.PYTHON)
try:
    sandbox.prepare_workdir(files)
    result = sandbox.run_command("python main.py")
finally:
    manager.release_sandbox(Language.PYTHON, sandbox)
```

### Context Manager (Recommended)

```python
manager = get_sandbox_manager()
with manager.acquire_sandbox(Language.PYTHON) as sandbox:
    sandbox.prepare_workdir(files)
    result = sandbox.run_command("python main.py")
# Automatically released, even on exception
```

### Destroy on Fatal Error

```python
manager = get_sandbox_manager()
sandbox = manager.get_sandbox(Language.PYTHON)
try:
    result = sandbox.run_command("python main.py", timeout=30)
    if result.category == ResponseCategory.TIMEOUT:
        manager.destroy_sandbox(Language.PYTHON, sandbox)
        return  # Don't release — it's already destroyed
except Exception:
    manager.destroy_sandbox(Language.PYTHON, sandbox)
    raise
manager.release_sandbox(Language.PYTHON, sandbox)
```

---

## Monitoring

Get pool statistics:

```python
stats = manager.get_pool_stats()
# {
#   "python": { "idle": 2, "active": 1, "total": 3, "pool_size": 3, "scale_limit": 10, "utilization": 33.3 },
#   "java":   { "idle": 3, "active": 0, "total": 3, "pool_size": 3, "scale_limit": 10, "utilization": 0.0 },
#   ...
# }
```

The monitor thread logs load warnings automatically:
- **≥90% utilization:** 🚨 `HIGH LOAD` warning
- **≥70% utilization:** ⚠️ `MODERATE LOAD` warning
- **Otherwise:** 📊 periodic stats

