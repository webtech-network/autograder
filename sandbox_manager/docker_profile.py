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
"""
from typing import Dict

from docker.types.containers import Ulimit

from sandbox_manager.models.sandbox_models import Language

GVISOR_RUNTIME = "runsc"

MEMORY_LIMIT = "128m"
NANO_CPUS = 500_000_000  # 0.5 CPU
PIDS_LIMIT = 64
FILE_SIZE_LIMIT_BYTES = 10_000_000
WORKSPACE_TMPFS = "rw,size=64m,exec,mode=1777"   # /app: submission and artifacts
FIXTURE_TMPFS = "rw,size=32m,noexec"             # /tmp: fixtures, never executable
FIXTURE_TMPFS_BYTES = 32 * 1024 * 1024


def container_options(language: Language, name: str, labels: Dict[str, str]) -> dict:
    """Keyword arguments for ``client.containers.run`` without a runtime."""
    return {
        "image": language.image,
        "name": name,
        "detach": True,
        "command": "sleep infinity",  # Keep the container alive for exec commands.
        "mem_limit": MEMORY_LIMIT,
        "memswap_limit": MEMORY_LIMIT,
        "nano_cpus": NANO_CPUS,
        "pids_limit": PIDS_LIMIT,
        "tmpfs": {"/app": WORKSPACE_TMPFS, "/tmp": FIXTURE_TMPFS},
        "network_mode": "none",
        "cap_drop": ["ALL"],
        "ulimits": [Ulimit(name="fsize", soft=FILE_SIZE_LIMIT_BYTES, hard=FILE_SIZE_LIMIT_BYTES)],
        "labels": dict(labels),
    }


def is_missing_runtime_error(exc: Exception) -> bool:
    """Whether the daemon rejected the gVisor runtime (then use the default runtime)."""
    text = str(exc).lower()
    return "unknown or invalid runtime name" in text or GVISOR_RUNTIME in text
