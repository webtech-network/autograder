"""The one Docker profile for pooled sandboxes.

Every limit and isolation option is declared here once. The host chooses the
OCI runtime explicitly (``general.runtime`` in ``sandbox_config.yml``): gVisor
(``runsc``) or ``runc``. **The runtime argument is the only difference between
the two**; a host never switches runtime on its own.

Storage: the root filesystem is read-only, so nothing a submission writes
reaches the container's writable layer on host disk. The writable paths are
the in-memory tmpfs mounts in :data:`WRITABLE_PATHS`, each bounded by its size,
charged to the container's memory limit and gone with the container, plus, under
runc only, the kernel's POSIX message-queue mount :data:`MQUEUE_PATH`.
``/app`` and ``/tmp`` use ``mode=1777`` so the unprivileged ``sandbox`` user can
write them under both runtimes (runc mounts a tmpfs ``root:root 0755``
otherwise); the image's ``VOLUME /app`` never becomes an anonymous volume.

Control and submission identities: PID 1 (Docker's init, which reaps orphans,
running ``sleep infinity``) and every control exec that may run beside a
submission's processes (termination sweep, output and artifact readback) run
as ``root``. Submission processes run as the image's unprivileged ``sandbox``
user, so they cannot signal PID 1 or a control exec. ``root`` keeps exactly
two capabilities: ``KILL`` to end every ``sandbox`` process, and
``DAC_OVERRIDE`` to read back and remove files whatever permissions the
submission gave them. A non-root process holds no capabilities and
``no-new-privileges`` stops it from gaining any.
"""
from typing import Dict, Tuple

from docker.types.containers import Ulimit

GVISOR_RUNTIME = "runsc"
RUNC_RUNTIME = "runc"
#: The OCI runtimes a host may choose; gVisor first, as the recommended one.
RUNTIMES: Tuple[str, ...] = (GVISOR_RUNTIME, RUNC_RUNTIME)

MIB = 1024 * 1024
MEMORY_LIMIT_BYTES = 128 * MIB                   # memory + swap; tmpfs pages count against it
NANO_CPUS = 500_000_000  # 0.5 CPU
PIDS_LIMIT = 64
FILE_SIZE_LIMIT_BYTES = 10_000_000
WORKSPACE_TMPFS_BYTES = 64 * MIB                 # /app: submission and artifacts
FIXTURE_TMPFS_BYTES = 32 * MIB                   # /tmp: fixtures and run files, never executable
SHM_SIZE_BYTES = 64 * MIB                        # /dev/shm (Docker's default, declared)
#: Every path a submission can write, with its size bound in bytes. All of them
#: are tmpfs: memory-backed, charged to the memory limit, removed with the container.
WRITABLE_PATHS: Dict[str, int] = {"/app": WORKSPACE_TMPFS_BYTES, "/tmp": FIXTURE_TMPFS_BYTES,
                                  "/dev/shm": SHM_SIZE_BYTES}
#: runc (not gVisor) also mounts the POSIX message-queue filesystem, writable by
#: every user. It stores no file bytes: queues live in kernel memory, bounded per
#: user by RLIMIT_MSGQUEUE (Docker's 819200 bytes), never on host disk.
MQUEUE_PATH = "/dev/mqueue"
CONTROL_USER = "root"
CONTROL_CAPABILITIES = ["DAC_OVERRIDE", "KILL"]


def container_options(image: str, name: str, labels: Dict[str, str]) -> dict:
    """Keyword arguments for ``client.containers.run``, except the host's ``runtime``.

    ``image`` comes from the host runtime profile (``SandboxPoolConfig.image``).
    """
    return {
        "image": image,
        "name": name,
        "detach": True,
        "user": CONTROL_USER,
        "init": True,                 # PID 1 reaps orphans: killed processes never pin the pids limit.
        "command": "sleep infinity",  # Keep the container alive for exec commands.
        "mem_limit": MEMORY_LIMIT_BYTES,
        "memswap_limit": MEMORY_LIMIT_BYTES,
        "nano_cpus": NANO_CPUS,
        "pids_limit": PIDS_LIMIT,
        "read_only": True,            # No write reaches the writable layer on host disk.
        "tmpfs": {"/app": f"rw,size={WORKSPACE_TMPFS_BYTES},exec,mode=1777",
                  "/tmp": f"rw,size={FIXTURE_TMPFS_BYTES},noexec,mode=1777"},
        "shm_size": SHM_SIZE_BYTES,
        "network_mode": "none",
        "cap_drop": ["ALL"],
        "cap_add": list(CONTROL_CAPABILITIES),
        "security_opt": ["no-new-privileges"],
        "ulimits": [Ulimit(name="fsize", soft=FILE_SIZE_LIMIT_BYTES, hard=FILE_SIZE_LIMIT_BYTES)],
        "labels": dict(labels),
    }

