"""One language's warm containers and the records that own them until destruction.

A container is always in exactly one record set until Docker confirms removal:

``idle`` (warm) -> ``active`` (leased) -> ``closing`` -> confirmed (record dropped)

``closing`` records are kept when Docker fails, retried with capped backoff by
the manager's monitor, counted against ``scale_limit`` and reported in stats.
"""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Set

import docker
from docker.client import DockerClient

from sandbox_manager.errors import Disposal, SandboxCapacityError, SandboxCleanupError
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language, SandboxState
from sandbox_manager.ownership import APP_VALUE, LABEL_APP, LABEL_OWNER
from sandbox_manager.sandbox_container import SandboxContainer

LABEL_VERSION = "autograder.sandbox.version"
LABEL_LANGUAGE = "autograder.sandbox.language"
LABEL_POOL_ID = "autograder.sandbox.pool_id"
LABEL_CREATED_AT = "autograder.sandbox.created_at"
SANDBOX_VERSION = "2.0"
MAX_RETRY_DELAY_SECONDS = 60.0

logger = logging.getLogger(__name__)


@dataclass
class CleanupRecord:
    """A container whose destruction has started but is not yet confirmed."""
    reason: str
    attempts: int = 0
    last_error: Optional[str] = None
    next_attempt: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class LanguagePool:
    def __init__(self, language: Language, config: SandboxPoolConfig, client: DockerClient, *,
                 owner_id: str, runtime: str):
        self.language = language
        self.config = config
        self.client = client
        self.owner_id = owner_id
        self.runtime = runtime
        self.pool_id = owner_id  # container names stay unique per owner
        self._sandbox_seq = 0
        self.closed = False

        self.idle_sandboxes: deque[SandboxContainer] = deque()
        self.active_sandboxes: Set[SandboxContainer] = set()
        self.closing: Dict[SandboxContainer, CleanupRecord] = {}
        self.lock = threading.Lock()

    # ----- leasing -------------------------------------------------------------------
    def _total(self) -> int:
        return len(self.idle_sandboxes) + len(self.active_sandboxes) + len(self.closing)

    def acquire(self) -> SandboxContainer:
        with self.lock:
            if self.closed:
                raise SandboxCapacityError(f"The {self.language.value} pool is shut down")
            if self.idle_sandboxes:
                sandbox = self.idle_sandboxes.popleft()
            elif self._total() < self.config.scale_limit:
                try:
                    sandbox = self._create_sandbox()
                except Exception as exc:
                    logger.exception("[%s] scale-up failed", self.language.value)
                    raise SandboxCapacityError(f"Failed to create a {self.language.value} sandbox") from exc
            else:
                logger.warning("[%s] all %s sandboxes are leased or closing (scale_limit %s)",
                               self.language.value, self._total(), self.config.scale_limit)
                raise SandboxCapacityError(
                    f"No {self.language.value} sandbox is available (scale_limit {self.config.scale_limit})")
            sandbox.pickup()
            self.active_sandboxes.add(sandbox)
            return sandbox

    def dispose(self, sandbox: SandboxContainer) -> Disposal:
        """End a lease. Idempotent; raises ``SandboxCleanupError`` while unconfirmed."""
        with self.lock:
            if sandbox in self.active_sandboxes:
                record = self._start_closing(sandbox, "disposed")
            elif sandbox in self.closing:
                record = self.closing[sandbox]
            elif sandbox.state is SandboxState.STOPPED:
                return Disposal.ALREADY_DISPOSED
            else:
                raise ValueError("Sandbox is not leased from this pool")
        return self._destroy(sandbox, record)

    # ----- destruction ---------------------------------------------------------------
    def _start_closing(self, sandbox: SandboxContainer, reason: str) -> CleanupRecord:
        """Move a record to ``closing``; caller holds ``self.lock``."""
        self.active_sandboxes.discard(sandbox)
        try:
            self.idle_sandboxes.remove(sandbox)
        except ValueError:
            pass
        sandbox.state = SandboxState.CLOSING
        record = self.closing[sandbox] = CleanupRecord(reason=reason)
        return record

    def _destroy(self, sandbox: SandboxContainer, record: CleanupRecord) -> Disposal:
        with record.lock:
            if sandbox.state is SandboxState.STOPPED:
                return Disposal.ALREADY_DISPOSED
            try:
                sandbox.container_ref.remove(force=True, v=True)
            except docker.errors.NotFound:
                pass  # already gone: destruction is confirmed
            except Exception as exc:
                record.attempts += 1
                record.last_error = repr(exc)
                record.next_attempt = time.monotonic() + min(MAX_RETRY_DELAY_SECONDS, 2.0 ** record.attempts)
                logger.error("[%s] sandbox %s cleanup failed (attempt %s, %s); record retained for retry: %s",
                             self.language.value, sandbox.container_ref.id[:12], record.attempts,
                             record.reason, exc)
                raise SandboxCleanupError("Sandbox disposal was not confirmed; its owner retains it for retry") from exc
            sandbox.state = SandboxState.STOPPED
        with self.lock:
            self.closing.pop(sandbox, None)
        logger.info("[%s] sandbox %s destroyed (%s)", self.language.value, sandbox.container_ref.id[:12], record.reason)
        return Disposal.DISPOSED

    def _try_destroy(self, sandbox: SandboxContainer, record: CleanupRecord) -> bool:
        try:
            self._destroy(sandbox, record)
            return True
        except SandboxCleanupError:
            return False

    def retry_cleanup(self) -> None:
        """Retry due ``closing`` records (called by the monitor)."""
        now = time.monotonic()
        with self.lock:
            due = [(sandbox, record) for sandbox, record in self.closing.items() if record.next_attempt <= now]
        for sandbox, record in due:
            self._try_destroy(sandbox, record)

    def expire_leases(self) -> None:
        """Dispose leases older than ``running_timeout``; the holder sees an expired sandbox."""
        now = datetime.now()
        with self.lock:
            expired = [sandbox for sandbox in self.active_sandboxes
                       if (now - sandbox.last_updated).total_seconds() > self.config.running_timeout]
            records = [(sandbox, self._start_closing(sandbox, "lease expired")) for sandbox in expired]
        for sandbox, record in records:
            logger.warning("[%s] lease on sandbox %s exceeded %ss; disposing it",
                           self.language.value, sandbox.container_ref.id[:12], self.config.running_timeout)
            self._try_destroy(sandbox, record)

    def scale_down_idle(self) -> None:
        now = datetime.now()
        with self.lock:
            surplus = len(self.idle_sandboxes) - self.config.pool_size
            stale = [sandbox for sandbox in self.idle_sandboxes
                     if (now - sandbox.created_at).total_seconds() > self.config.idle_timeout][:max(surplus, 0)]
            records = [(sandbox, self._start_closing(sandbox, "idle scale-down")) for sandbox in stale]
        for sandbox, record in records:
            self._try_destroy(sandbox, record)

    def replenish(self) -> None:
        """Keep ``pool_size`` warm sandboxes without exceeding ``scale_limit``."""
        with self.lock:
            while (not self.closed and len(self.idle_sandboxes) < self.config.pool_size
                   and self._total() < self.config.scale_limit):
                try:
                    self.idle_sandboxes.append(self._create_sandbox())
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("[%s] replenish failed", self.language.value)
                    break

    def monitor(self) -> None:
        self.retry_cleanup()
        self.expire_leases()
        self.scale_down_idle()
        self.replenish()

    def shutdown(self) -> int:
        """Stop leasing and attempt to destroy every owned container. Returns pending count.

        Safe to repeat: a later call retries the records that are still pending.
        """
        with self.lock:
            self.closed = True
            for sandbox in list(self.idle_sandboxes) + list(self.active_sandboxes):
                self._start_closing(sandbox, "shutdown")
            pending = list(self.closing.items())
        for sandbox, record in pending:
            self._try_destroy(sandbox, record)
        with self.lock:
            return len(self.closing)

    # ----- observability -------------------------------------------------------------
    def get_stats(self) -> dict:
        with self.lock:
            total = self._total()
            return {
                "language": self.language.value,
                "idle": len(self.idle_sandboxes),
                "active": len(self.active_sandboxes),
                "cleanup_pending": len(self.closing),
                "total": total,
                "pool_size": self.config.pool_size,
                "scale_limit": self.config.scale_limit,
                "utilization": len(self.active_sandboxes) / total * 100 if total else 0,
            }

    def cleanup_problems(self) -> list:
        with self.lock:
            return [{"language": self.language.value, "container_id": sandbox.container_ref.id[:12],
                     "reason": record.reason, "attempts": record.attempts, "last_error": record.last_error}
                    for sandbox, record in self.closing.items() if record.attempts]

    # ----- creation ------------------------------------------------------------------
    def _create_sandbox(self) -> SandboxContainer:
        """Create one container from the runtime profile; caller holds ``self.lock``."""
        name = self._build_container_name()
        labels = {
            LABEL_APP: APP_VALUE,
            LABEL_OWNER: self.owner_id,
            LABEL_VERSION: SANDBOX_VERSION,
            LABEL_LANGUAGE: self.language.value,
            LABEL_POOL_ID: self.pool_id,
            LABEL_CREATED_AT: datetime.now().isoformat(),
        }
        try:
            container = self.client.containers.run(
                image=self.language.image, name=name, labels=labels,
                **self.config.profile.container_options(self.runtime))
        except Exception:
            # ``run`` may have created the container before start failed.
            try:
                self.client.containers.get(name).remove(force=True, v=True)
            except Exception:  # pylint: disable=broad-exception-caught
                pass  # absent, or swept by the owner label at shutdown/reclamation
            raise
        logger.info("[%s] created sandbox %s (%s, runtime %s)", self.language.value, name,
                    container.id[:12], self.runtime)
        return SandboxContainer(language=self.language, container_ref=container)

    def _build_container_name(self) -> str:
        """Deterministic container name: ag-sbx-{lang}-{owner8}-{seq4}."""
        self._sandbox_seq += 1
        return f"ag-sbx-{self.language.value}-{self.pool_id[:8]}-{self._sandbox_seq:04d}"
