# Sandbox Management

## What it is

Sandbox management is the isolation layer used when templates require code execution.

It is implemented by `SandboxManager`, which coordinates per-language `LanguagePool` instances and `SandboxContainer` objects.

## Why it matters

- Safety: untrusted student code runs in constrained containers.
- Performance: warm pools remove most container cold-start delay.
- Reliability: lifecycle controls avoid resource leaks and stale execution environments.

## How it works

1. The host (web API, sandbox control API, GitHub Action) constructs the manager
   and owns its shutdown; the library installs no signal handlers.
2. Startup reclaims containers whose owner is provably dead on this host.
3. Each pool pre-warms `pool_size` containers.
4. Grading requests acquire an idle sandbox or scale up until `scale_limit`.
5. Every used container is disposed (never reused). Docker must confirm removal;
   failed removals are quarantined, reported and retried.
6. The monitor thread enforces timeouts, retries quarantined removals and replenishes.

## Resource and isolation controls

Current container setup includes strict controls such as:

- memory limits
- CPU limits
- process count limits
- disabled network mode
- dropped Linux capabilities

Runtime prefers gVisor (`runsc`) when available and falls back to default runtime when unavailable.

## Operational tuning

| Goal | Main knobs |
|------|------------|
| Faster first response | Increase `pool_size` |
| Higher concurrency | Increase `scale_limit` |
| Lower idle resource usage | Lower `idle_timeout` |
| Faster stuck-process recovery | Lower `running_timeout` |

These values are defined in `sandbox_config.yml`.

## Common mistakes

- Publishing the sandbox control API port or running it without `SANDBOX_API_TOKEN`
- Running the control API with more than one worker (handles are in-process)
- Aggressive pool downsizing that causes repeated cold starts
- Raising scale limits without host capacity checks

## Continue reading

- [Sandbox ownership and private control API](../contracts/SANDBOX.md)
- [Sandbox Manager Internals](../architecture/sandbox_manager.md)
- [Pipeline Step: Sandbox](../pipeline/03-sandbox.md)
