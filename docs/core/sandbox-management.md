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
3. Each pool pre-warms `pool_size` idle containers.
4. Every acquisition (grading or deliberate execution, any language) first takes a
   slot of the one host budget `max_sandboxes`, waiting in arrival order when all
   slots are held, then takes an idle container or creates one outside any lock.
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

The root filesystem is read-only; submissions write only bounded tmpfs mounts. The OCI runtime is the host's
explicit `general.runtime` (`runsc` for gVisor, or `runc`), never a fallback. See
[SANDBOX.md](../contracts/SANDBOX.md#isolation-profile-and-runtime) for the guarantees per environment.

## Operational tuning

| Goal | Main knobs |
|------|------------|
| Faster first response | Increase `pool_size` |
| Higher concurrency (up to the CPU knee) | Increase `max_sandboxes` |
| Accept definitions with more or longer processes | Raise `running_timeout` (the host maximum; each sandbox lives its definition's budget) |

These values are defined in `sandbox_config.yml`.

## Common mistakes

- Publishing the sandbox control API port or running it without `SANDBOX_API_TOKEN`
- Running the control API with more than one worker (handles are in-process)
- Aggressive pool downsizing that causes repeated cold starts
- Raising scale limits without host capacity checks

## Continue reading

- [Sandbox ownership and private control API](../contracts/SANDBOX.md)
- [Sandbox Manager Internals](../architecture/sandbox_manager.md)
- [Execution sessions](../pipeline/03-sandbox.md)
