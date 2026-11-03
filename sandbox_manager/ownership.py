"""Owner leases for sandbox containers.

Every container created by a :class:`~sandbox_manager.manager.SandboxManager`
carries the application label plus the identity of the manager that owns it:

* ``autograder.sandbox.owner``: random owner id, unique per manager instance;
* ``autograder.sandbox.owner_host``: hostname of the owning process;
* ``autograder.sandbox.owner_process``: ``<boot_id>:<pid>:<start_ticks>``.

A container may be reclaimed automatically only when its owner is *provably*
dead from this host's point of view: the owner ran on this hostname and either
the kernel has rebooted since (different boot id) or the owning pid is no longer
running with the recorded start time. Containers owned by another hostname, by a
live process, or without owner labels (legacy) are never touched automatically;
operators use ``python -m sandbox_manager.reclaim`` for those.

The hostname must identify one PID namespace. Compose gives the single sandbox
service a fixed ``hostname`` so a restarted container recognises its previous
incarnation; never run two managers with the same hostname in different PID
namespaces.
"""
from __future__ import annotations

import logging
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

LABEL_APP = "autograder.sandbox.app"
APP_LABEL_VALUE = "autograder-sandbox"
LABEL_OWNER = "autograder.sandbox.owner"
LABEL_OWNER_HOST = "autograder.sandbox.owner_host"
LABEL_OWNER_PROCESS = "autograder.sandbox.owner_process"

APP_FILTER = {"label": f"{LABEL_APP}={APP_LABEL_VALUE}"}
_PROC = "/proc"


def read_boot_id(proc_root: str = _PROC) -> Optional[str]:
    """Kernel boot id, or None where /proc does not provide it."""
    try:
        with open(os.path.join(proc_root, "sys/kernel/random/boot_id"), encoding="ascii") as handle:
            value = handle.read().strip()
        return value or None
    except OSError:
        return None


def process_start_ticks(pid: int, proc_root: str = _PROC) -> Optional[str]:
    """Start time of ``pid`` in clock ticks since boot (field 22 of /proc/<pid>/stat).

    Returns None when the process does not exist or /proc is unavailable.
    """
    try:
        with open(os.path.join(proc_root, str(pid), "stat"), encoding="ascii", errors="replace") as handle:
            data = handle.read()
    except OSError:
        return None
    # The command name (field 2) is parenthesised and may contain spaces.
    fields = data[data.rfind(")") + 2:].split()
    # fields[0] is field 3 (state); field 22 (starttime) is fields[19].
    return fields[19] if len(fields) > 19 else None


@dataclass(frozen=True)
class OwnerIdentity:
    """Identity labelled on every container a manager creates."""
    owner_id: str
    hostname: str
    boot_id: Optional[str]
    pid: int
    start_ticks: Optional[str]

    @classmethod
    def current(cls, proc_root: str = _PROC) -> "OwnerIdentity":
        pid = os.getpid()
        return cls(owner_id=uuid.uuid4().hex, hostname=socket.gethostname(),
                   boot_id=read_boot_id(proc_root), pid=pid,
                   start_ticks=process_start_ticks(pid, proc_root))

    @property
    def process_token(self) -> str:
        return f"{self.boot_id or 'unknown'}:{self.pid}:{self.start_ticks or 'unknown'}"

    def labels(self) -> Dict[str, str]:
        return {
            LABEL_APP: APP_LABEL_VALUE,
            LABEL_OWNER: self.owner_id,
            LABEL_OWNER_HOST: self.hostname,
            LABEL_OWNER_PROCESS: self.process_token,
        }

    @property
    def filter(self) -> Dict[str, List[str]]:
        """Docker filter selecting exactly this owner's containers."""
        return {"label": [f"{LABEL_APP}={APP_LABEL_VALUE}", f"{LABEL_OWNER}={self.owner_id}"]}


def owner_status(labels: Dict[str, str], local: OwnerIdentity, proc_root: str = _PROC) -> str:
    """Classify a container's owner as seen from ``local``.

    Returns one of ``"legacy"`` (no owner labels), ``"remote"`` (another
    hostname: liveness unknown), ``"unknown"`` (same host, but liveness cannot
    be established), ``"alive"`` or ``"dead"``. Only ``"dead"`` is reclaimed
    automatically.
    """
    owner = labels.get(LABEL_OWNER)
    host = labels.get(LABEL_OWNER_HOST)
    token = labels.get(LABEL_OWNER_PROCESS)
    if not owner or not host or not token:
        return "legacy"
    if host != local.hostname:
        return "remote"
    parts = token.split(":")
    if len(parts) != 3 or local.boot_id is None:
        return "unknown"
    boot_id, pid_text, start = parts
    if boot_id == "unknown":
        return "unknown"
    if boot_id != local.boot_id:
        return "dead"  # The kernel rebooted: every process of that boot is gone.
    try:
        pid = int(pid_text)
    except ValueError:
        return "unknown"
    if start == "unknown":
        return "unknown"
    current = process_start_ticks(pid, proc_root)
    if current is None or current != start:
        return "dead"  # pid gone, or reused by a different process.
    return "alive"


def _remove(container) -> bool:
    import docker
    try:
        container.remove(force=True, v=True)
        return True
    except docker.errors.NotFound:
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to remove sandbox container %s", getattr(container, "name", "?"))
        return False


def list_app_containers(client) -> list:
    return client.containers.list(all=True, filters=APP_FILTER)


def reclaim_dead_owners(client, local: OwnerIdentity, proc_root: str = _PROC) -> List[str]:
    """Remove containers whose owner is provably dead. Never touches other owners."""
    removed = []
    try:
        containers = list_app_containers(client)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Orphan reclamation could not list sandbox containers")
        return removed
    skipped: Dict[str, int] = {}
    for container in containers:
        labels = container.labels or {}
        if labels.get(LABEL_OWNER) == local.owner_id:
            continue
        status = owner_status(labels, local, proc_root)
        if status != "dead":
            skipped[status] = skipped.get(status, 0) + 1
            continue
        logger.warning("Reclaiming sandbox %s of dead owner %s (%s)", container.name,
                       labels.get(LABEL_OWNER), labels.get(LABEL_OWNER_PROCESS))
        if _remove(container):
            removed.append(container.id)
    if skipped:
        logger.info("Orphan reclamation left containers of other owners untouched: %s", skipped)
    return removed


def reclaim_selected(client, *, owner: Optional[str] = None, dead_host: Optional[str] = None,
                     legacy: bool = False, local: Optional[OwnerIdentity] = None,
                     dry_run: bool = False, proc_root: str = _PROC) -> List[Dict[str, str]]:
    """Operator-selected reclamation. Refuses containers whose owner is visibly alive here."""
    local = local or OwnerIdentity.current(proc_root)
    selected = []
    for container in list_app_containers(client):
        labels = container.labels or {}
        status = owner_status(labels, local, proc_root)
        matches = ((owner is not None and labels.get(LABEL_OWNER) == owner)
                   or (dead_host is not None and labels.get(LABEL_OWNER_HOST) == dead_host)
                   or (legacy and status == "legacy"))
        if not matches:
            continue
        if status == "alive":
            logger.error("Refusing to reclaim %s: owner %s is running on this host",
                         container.name, labels.get(LABEL_OWNER))
            continue
        row = {"id": container.id, "name": container.name, "owner": labels.get(LABEL_OWNER, ""),
               "host": labels.get(LABEL_OWNER_HOST, ""), "status": status}
        if not dry_run and not _remove(container):
            row["status"] = "remove_failed"
        selected.append(row)
    return selected


def describe(client, local: Optional[OwnerIdentity] = None, proc_root: str = _PROC) -> Iterable[Dict[str, str]]:
    local = local or OwnerIdentity.current(proc_root)
    for container in list_app_containers(client):
        labels = container.labels or {}
        yield {"id": container.id[:12], "name": container.name,
               "owner": labels.get(LABEL_OWNER, "-"), "host": labels.get(LABEL_OWNER_HOST, "-"),
               "status": owner_status(labels, local, proc_root)}
