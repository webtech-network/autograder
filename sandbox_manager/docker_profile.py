"""The one Docker profile for pooled sandboxes.

Every limit and isolation option is declared here once. Sandboxes prefer the
gVisor runtime (``runsc``); when the daemon does not know that runtime, the same
options are used with Docker's default runtime. **The only allowed difference
between the two paths is the absent ``runtime`` argument.**

History: the default-runtime path used to omit the ``/app`` tmpfs. A tmpfs is
mounted ``root:root 0755`` by runc, so the unprivileged ``sandbox`` user could
not write submissions there, and the image's ``VOLUME /app`` silently became an
unbounded anonymous volume that ``remove()`` without ``v=True`` leaked. Mounting
``/app`` with ``mode=1777`` keeps it writable under both runtimes, bounded by
size, and removed with the container.

Lifetime: no container outlives a bound it enforces itself, whether or not its
owner is alive. PID 1 (Docker's init) runs ``sleep <bound>``, the outer bound of
an idle container. When a sandbox is granted, a control exec arms its absolute
lifetime (:data:`LIFETIME`): it sleeps, then kills every other process, so
PID 1's child exits and the container stops with nothing left running. Owner
reclamation only removes stopped records.

Control and submission identities: PID 1 (Docker's init, which reaps orphans,
running ``sleep``) and every control exec that may run beside a
submission's processes (termination sweep, output and artifact readback) run
as ``root``. Submission processes run as the image's unprivileged ``sandbox``
user, so they cannot signal PID 1 or a control exec. ``root`` keeps exactly
two capabilities: ``KILL`` to end every ``sandbox`` process, and
``DAC_OVERRIDE`` to read back and remove files whatever permissions the
submission gave them. A non-root process holds no capabilities and
``no-new-privileges`` stops it from gaining any.
"""
from typing import Dict

from docker.types.containers import Ulimit

GVISOR_RUNTIME = "runsc"

MEMORY_LIMIT = "128m"
NANO_CPUS = 500_000_000  # 0.5 CPU
PIDS_LIMIT = 64
FILE_SIZE_LIMIT_BYTES = 10_000_000
WORKSPACE_TMPFS = "rw,size=64m,exec,mode=1777"   # /app: submission and artifacts
FIXTURE_TMPFS = "rw,size=32m,noexec"             # /tmp: fixtures, never executable
FIXTURE_TMPFS_BYTES = 32 * 1024 * 1024
CONTROL_USER = "root"
CONTROL_CAPABILITIES = ["DAC_OVERRIDE", "KILL"]


# Run as root, which the submission cannot signal: $1 seconds after the grant,
# kill every process except PID 1 and this shell (kill -1 needs no fork, so a
# submission at its pids limit cannot stop it). PID 1's child dies, so PID 1
# exits and the container stops.
LIFETIME = 'sleep "$1"; kill -KILL -1'


def container_options(image: str, name: str, labels: Dict[str, str], bound_seconds: int) -> dict:
    """Keyword arguments for ``client.containers.run`` without a runtime.

    ``image`` comes from the host runtime profile (``SandboxPoolConfig.image``);
    the container stops by itself ``bound_seconds`` after it starts.
    """
    return {
        "image": image,
        "name": name,
        "detach": True,
        "user": CONTROL_USER,
        "init": True,                 # PID 1 reaps orphans: killed processes never pin the pids limit.
        "command": ["sleep", str(int(bound_seconds))],  # Alive for exec commands, never forever.
        "mem_limit": MEMORY_LIMIT,
        "memswap_limit": MEMORY_LIMIT,
        "nano_cpus": NANO_CPUS,
        "pids_limit": PIDS_LIMIT,
        "tmpfs": {"/app": WORKSPACE_TMPFS, "/tmp": FIXTURE_TMPFS},
        "network_mode": "none",
        "cap_drop": ["ALL"],
        "cap_add": list(CONTROL_CAPABILITIES),
        "security_opt": ["no-new-privileges"],
        "ulimits": [Ulimit(name="fsize", soft=FILE_SIZE_LIMIT_BYTES, hard=FILE_SIZE_LIMIT_BYTES)],
        "labels": dict(labels),
    }


def is_missing_runtime_error(exc: Exception) -> bool:
    """Whether the daemon rejected the gVisor runtime (then use the default runtime)."""
    text = str(exc).lower()
    return "unknown or invalid runtime name" in text or GVISOR_RUNTIME in text
