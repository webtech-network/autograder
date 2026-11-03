# Sandbox Management

## What it is

Sandbox management is the isolation layer used when templates require code execution.

It is implemented by `SandboxManager`, which coordinates per-language `LanguagePool` instances and `SandboxContainer` objects.

## Why it matters

- Safety: untrusted student code runs in constrained containers.
- Performance: warm pools remove most container cold-start delay.
- Reliability: lifecycle controls avoid resource leaks and stale execution environments.

## How it works

1. The host starts one manager. It takes Docker ownership and reclaims only containers whose owner is provably dead.
2. Each pool prewarms `pool_size` containers.
3. Each execution session leases an idle sandbox, or scales up until `scale_limit`.
4. Closing the session destroys the container. Used containers are never reused. A failed removal keeps the record and retries it.
5. The monitor thread retries cleanup, expires leases older than `running_timeout`, and replenishes the pool.

## Resource and isolation controls

Current container setup includes strict controls such as:

- memory limits
- CPU limits
- process count limits
- disabled network mode
- dropped Linux capabilities

All limits and the runtime policy come from the `runtime:` section of `sandbox_config.yml`.
`auto` prefers gVisor (`runsc`) when Docker registers it and otherwise uses runc. The isolation
kernel is the only difference between them. See [Sandbox ownership](../contracts/SANDBOX.md).

## Operational tuning

| Goal | Main knobs |
|------|------------|
| Faster first response | Increase `pool_size` |
| Higher concurrency | Increase `scale_limit` |
| Lower idle resource usage | Lower `idle_timeout` |
| Faster recovery of abandoned leases | Lower `running_timeout` (maximum lease duration) |

These values are defined in `sandbox_config.yml`.

## Common mistakes

- Running the control API with several workers or replicas (lease handles are in-memory)
- Publishing the control API port instead of keeping it on a private network
- Aggressive pool downsizing that causes repeated cold starts
- Raising scale limits without host capacity checks

## Continue reading

- [Sandbox ownership and the control API](../contracts/SANDBOX.md)
- [Sandbox Manager Internals](../architecture/sandbox_manager.md)
- [Execution sessions](../pipeline/03-sandbox.md)
