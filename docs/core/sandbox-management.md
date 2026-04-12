# Sandbox Management

## What it is

Sandbox management is the isolation layer used when templates require code execution.

It is implemented by `SandboxManager`, which coordinates per-language `LanguagePool` instances and `SandboxContainer` objects.

## Why it matters

- Safety: untrusted student code runs in constrained containers.
- Performance: warm pools remove most container cold-start delay.
- Reliability: lifecycle controls avoid resource leaks and stale execution environments.

## How it works

1. App startup initializes one pool per configured language.
2. Each pool pre-warms `pool_size` containers.
3. Grading requests acquire an idle sandbox or scale up until `scale_limit`.
4. Containers are released back to the pool after execution.
5. Monitor thread enforces timeout-based cleanup and replenishment.

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

- Treating a timeout sandbox as reusable after fatal execution behavior
- Aggressive pool downsizing that causes repeated cold starts
- Raising scale limits without host capacity checks

## Continue reading

- [Sandbox Manager Internals](../architecture/sandbox_manager.md)
- [Pipeline Step: Sandbox](../pipeline/03-sandbox.md)
