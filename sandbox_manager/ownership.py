"""Host ownership of sandbox containers and reclamation of provably dead owners.

Each running :class:`~sandbox_manager.manager.SandboxManager` holds an exclusive
``flock`` on ``<lease_dir>/<owner_id>.lease`` for its whole lifetime and labels
every container it creates with its ``owner_id``. The kernel releases the lock
when the owning process exits for any reason, including ``SIGKILL``.

Another host may reclaim an owner's containers only after it acquires that
owner's lock: that is the proof of death. An owner whose lease file is absent
(another machine, another lease directory, or a pre-ownership container) cannot
be proven dead, so its containers are left alone and reported.

Hosts that share one Docker daemon must share one lease directory
(``SANDBOX_LEASE_DIR``) for dead-owner recovery to work. ``flock`` locks belong
to an open file description, so two managers in one process are distinct
owners too.
"""
import fcntl
import json
import logging
import os
import re
import socket
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import docker

logger = logging.getLogger(__name__)

LABEL_APP = "autograder.sandbox.app"
APP_VALUE = "autograder-sandbox"
LABEL_OWNER = "autograder.sandbox.owner"
_OWNER_ID = re.compile(r"^[0-9a-f]{32}$")


def default_lease_dir() -> str:
    """``SANDBOX_LEASE_DIR`` or a per-machine temporary directory."""
    return os.environ.get("SANDBOX_LEASE_DIR") or os.path.join(tempfile.gettempdir(), "autograder-sandbox-leases")


def _lease_path(lease_dir: str, owner_id: str) -> str:
    return os.path.join(lease_dir, f"{owner_id}.lease")


class OwnerLease:
    """The live ownership record of one host-owned manager."""

    def __init__(self, lease_dir: str | None = None):
        self.lease_dir = lease_dir or default_lease_dir()
        self.owner_id = uuid.uuid4().hex
        self.path = _lease_path(self.lease_dir, self.owner_id)
        self._fd = None

    def acquire(self) -> None:
        os.makedirs(self.lease_dir, mode=0o700, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.write(fd, json.dumps({
                "owner_id": self.owner_id, "pid": os.getpid(), "hostname": socket.gethostname(),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }).encode())
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    def release(self, *, resources_remain: bool) -> None:
        """Unlock. Keep the file when resources remain so a later host reclaims them."""
        if self._fd is None:
            return
        try:
            if not resources_remain:
                try:
                    os.unlink(self.path)
                except FileNotFoundError:
                    pass
        finally:
            os.close(self._fd)  # closing the descriptor releases the flock
            self._fd = None

    @property
    def held(self) -> bool:
        return self._fd is not None


@dataclass
class ReclaimReport:
    """What startup reclamation did and what it deliberately left alone."""
    reclaimed: list = field(default_factory=list)       # container ids removed
    failed: list = field(default_factory=list)          # (container id, error) left for a later attempt
    live_owners: set = field(default_factory=set)       # owners holding their lock
    unverifiable: int = 0                               # containers whose owner cannot be proven dead


def reclaim_dead_owners(client, lease_dir: str, *, own_owner_id: str | None = None) -> ReclaimReport:
    """Remove containers of owners proven dead by an acquirable lease lock."""
    report = ReclaimReport()
    containers = client.containers.list(all=True, filters={"label": f"{LABEL_APP}={APP_VALUE}"})
    by_owner: dict[str, list] = {}
    for container in containers:
        owner = (container.labels or {}).get(LABEL_OWNER, "")
        if owner == own_owner_id:
            continue
        if not _OWNER_ID.match(owner) or not os.path.exists(_lease_path(lease_dir, owner)):
            report.unverifiable += 1
            continue
        by_owner.setdefault(owner, []).append(container)

    for owner, owned in by_owner.items():
        path = _lease_path(lease_dir, owner)
        try:
            fd = os.open(path, os.O_RDWR)
        except FileNotFoundError:
            report.unverifiable += len(owned)  # its owner shut down cleanly meanwhile
            continue
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                report.live_owners.add(owner)
                continue
            remaining = 0
            for container in owned:
                try:
                    container.remove(force=True, v=True)
                    report.reclaimed.append(container.id)
                except docker.errors.NotFound:
                    report.reclaimed.append(container.id)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    remaining += 1
                    report.failed.append((container.id, repr(exc)))
            if remaining == 0:
                os.unlink(path)
        finally:
            os.close(fd)

    if report.reclaimed:
        logger.warning("Reclaimed %d sandbox container(s) from dead owner(s)", len(report.reclaimed))
    if report.failed:
        logger.error("Could not reclaim %d dead-owner sandbox container(s); the lease file is kept "
                     "so the next host start retries: %s", len(report.failed), report.failed)
    if report.unverifiable:
        logger.info("Left %d sandbox container(s) whose owner cannot be proven dead "
                    "(another lease directory, another machine, or created before ownership labels)",
                    report.unverifiable)
    return report
