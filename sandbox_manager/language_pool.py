"""One language's sandbox pool: idle -> active -> closing -> (disposed | quarantined).

A used sandbox is never reused. :meth:`LanguagePool.dispose` is the only way a
tracked sandbox leaves the pool, and it forgets a sandbox only after Docker
confirms removal (``NotFound`` counts as confirmation). When Docker fails to
remove it, the sandbox is quarantined: it stays tracked, counts against
``scale_limit``, is reported in :meth:`get_stats`, and the monitor retries its
removal a bounded number of times with backoff.
"""
from datetime import datetime
import logging
import threading
import time
import uuid
from collections import deque
from typing import Callable, Dict, List, Optional, Set

import docker
from docker.client import DockerClient

from sandbox_manager.docker_profile import GVISOR_RUNTIME, container_options, is_missing_runtime_error
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import DisposalStatus, SandboxState
from autograder.models.language import Language
from sandbox_manager.ownership import OwnerIdentity
from sandbox_manager.sandbox_container import SandboxContainer

LABEL_VERSION = "autograder.sandbox.version"
LABEL_LANGUAGE = "autograder.sandbox.language"
LABEL_POOL_ID = "autograder.sandbox.pool_id"
LABEL_CREATED_AT = "autograder.sandbox.created_at"
SANDBOX_VERSION = "2"

DISPOSAL_BACKOFF_SECONDS = 1.0
DISPOSAL_BACKOFF_MAX_SECONDS = 60.0

logger = logging.getLogger(__name__)


class SandboxUnavailableError(ValueError):
    """The pool cannot hand out a sandbox now (capacity, shutdown or creation failure)."""


class LanguagePool:
    """Warm containers for one language, each used once and then disposed."""

    def __init__(self, language: Language, config: SandboxPoolConfig, client: DockerClient = None,
                 owner: Optional[OwnerIdentity] = None, clock: Callable[[], float] = time.monotonic):
        self.language = language
        self.config = config
        self.client = client
        self.owner = owner or OwnerIdentity.current()
        self.pool_id = str(uuid.uuid4())
        self._sandbox_seq = 0
        self._clock = clock
        self._gvisor_available = True
        self._closed = False

        self.idle_sandboxes: deque[SandboxContainer] = deque()
        self.active_sandboxes: Set[SandboxContainer] = set()
        self.closing_sandboxes: Set[SandboxContainer] = set()
        self.quarantined_sandboxes: Set[SandboxContainer] = set()
        self._monitor_counter = 0

        # Only blocks this pool; Docker removal always happens outside the lock.
        self.lock = threading.Lock()

        logger.info("[%s] POOL INITIALIZED - pool_size: %s, scale_limit: %s, pool_id: %s, owner: %s",
                    language, config.pool_size, config.scale_limit, self.pool_id[:8], self.owner.owner_id[:8])

    # ------------------------------------------------------------------ capacity
    def _tracked_count(self) -> int:
        """Every container this pool is responsible for, including unconfirmed removals."""
        return (len(self.idle_sandboxes) + len(self.active_sandboxes)
                + len(self.closing_sandboxes) + len(self.quarantined_sandboxes))

    def acquire(self) -> SandboxContainer:
        """Hand out an idle sandbox or create one within ``scale_limit``."""
        with self.lock:
            if self._closed:
                raise SandboxUnavailableError(f"Sandbox pool for {self.language.value} is shut down")
            if self.idle_sandboxes:
                sandbox = self.idle_sandboxes.popleft()
                sandbox.activate(self._clock())
                self.active_sandboxes.add(sandbox)
                logger.info("[%s] ACQUIRED from idle pool - sandbox_id: %s", self.language, sandbox.short_id)
                return sandbox

            total = self._tracked_count()
            if total < self.config.scale_limit:
                logger.info("[%s] NO IDLE SANDBOXES - Attempting scale-up...", self.language)
                try:
                    sandbox = self._create_sandbox()
                except Exception as e:
                    logger.exception("[%s] SCALE-UP FAILED - Error: %s", self.language, e)
                    raise SandboxUnavailableError(
                        f"Failed to create sandbox for language {self.language.value}") from e
                sandbox.activate(self._clock())
                self.active_sandboxes.add(sandbox)
                logger.info("[%s] SCALE-UP SUCCESS - created sandbox_id: %s", self.language, sandbox.short_id)
                return sandbox

            logger.warning("[%s] BOTTLENECK DETECTED - %s sandboxes tracked (scale_limit: %s, quarantined: %s)",
                           self.language, total, self.config.scale_limit, len(self.quarantined_sandboxes))
            raise SandboxUnavailableError(
                f"No idle sandboxes available for language {self.language.value}. "
                f"All {total} sandboxes are busy or awaiting disposal (scale_limit: {self.config.scale_limit})"
            )

    def replenish(self):
        """Keep ``pool_size`` idle sandboxes without exceeding ``scale_limit`` tracked ones."""
        with self.lock:
            if self._closed:
                return
            while (len(self.idle_sandboxes) < self.config.pool_size
                   and self._tracked_count() < self.config.scale_limit):
                try:
                    sandbox = self._create_sandbox()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.exception("[%s] REPLENISH FAILED - Error: %s", self.language, e)
                    break
                self.idle_sandboxes.append(sandbox)
                logger.info("[%s] REPLENISH SUCCESS - sandbox_id: %s", self.language, sandbox.short_id)

    # ------------------------------------------------------------------ disposal
    def dispose(self, sandbox: SandboxContainer) -> DisposalStatus:
        """Destroy a sandbox. Idempotent: repeated calls return a defined status.

        Raises ValueError only for a sandbox this pool never tracked.
        """
        with self.lock:
            if sandbox.state is SandboxState.DISPOSED:
                return DisposalStatus.ALREADY_DISPOSED
            if sandbox in self.closing_sandboxes:
                return DisposalStatus.CLOSING
            if sandbox in self.quarantined_sandboxes:
                return DisposalStatus.QUARANTINED
            if sandbox in self.active_sandboxes:
                self.active_sandboxes.remove(sandbox)
            elif sandbox in self.idle_sandboxes:
                self.idle_sandboxes.remove(sandbox)
            else:
                raise ValueError("Sandbox is not tracked by this pool")
            sandbox.state = SandboxState.CLOSING
            self.closing_sandboxes.add(sandbox)
        return self._remove_container(sandbox)

    def _remove_container(self, sandbox: SandboxContainer) -> DisposalStatus:
        """Attempt removal of a closing/quarantined sandbox; record the result under the lock."""
        sandbox_id = sandbox.short_id
        try:
            sandbox.container_ref.remove(force=True, v=True)
            error = None
        except docker.errors.NotFound:
            error = None  # Already gone: removal is confirmed.
        except Exception as exc:  # pylint: disable=broad-exception-caught
            error = exc
        with self.lock:
            self.closing_sandboxes.discard(sandbox)
            if error is None:
                self.quarantined_sandboxes.discard(sandbox)
                sandbox.state = SandboxState.DISPOSED
                sandbox.last_disposal_error = None
                logger.info("[%s] SANDBOX DISPOSED - container_id: %s", self.language, sandbox_id)
                return DisposalStatus.DISPOSED
            sandbox.state = SandboxState.QUARANTINED
            sandbox.disposal_attempts += 1
            sandbox.last_disposal_error = f"{type(error).__name__}: {error}"
            delay = min(DISPOSAL_BACKOFF_MAX_SECONDS,
                        DISPOSAL_BACKOFF_SECONDS * (2 ** (sandbox.disposal_attempts - 1)))
            sandbox.next_disposal_at = self._clock() + delay
            self.quarantined_sandboxes.add(sandbox)
            attempts = sandbox.disposal_attempts
        if attempts >= self.config.disposal_attempts:
            logger.error("[%s] SANDBOX QUARANTINED - removal of %s failed %s times; retries exhausted, "
                         "operator action required: %s", self.language, sandbox_id, attempts,
                         sandbox.last_disposal_error)
        else:
            logger.error("[%s] SANDBOX QUARANTINED - removal of %s failed (attempt %s/%s): %s",
                         self.language, sandbox_id, attempts, self.config.disposal_attempts,
                         sandbox.last_disposal_error)
        return DisposalStatus.QUARANTINED

    def retry_quarantined(self, final: bool = False) -> List[DisposalStatus]:
        """Retry removal of quarantined sandboxes whose backoff elapsed and attempts remain.

        ``final`` (shutdown) makes one more attempt for every quarantined sandbox.
        """
        now = self._clock()
        with self.lock:
            due = [sandbox for sandbox in self.quarantined_sandboxes
                   if final or (sandbox.disposal_attempts < self.config.disposal_attempts
                                and sandbox.next_disposal_at <= now)]
            for sandbox in due:
                self.quarantined_sandboxes.discard(sandbox)
                sandbox.state = SandboxState.CLOSING
                self.closing_sandboxes.add(sandbox)
        return [self._remove_container(sandbox) for sandbox in due]

    # ------------------------------------------------------------------ monitoring
    def check_ttls(self):
        """Dispose active sandboxes past ``running_timeout`` and surplus idle ones past ``idle_timeout``."""
        now = self._clock()
        with self.lock:
            expired_active = [sandbox for sandbox in self.active_sandboxes
                              if now - (sandbox.activated_at or sandbox.created_at) > self.config.running_timeout]
            surplus = len(self.idle_sandboxes) - self.config.pool_size
            expired_idle = [sandbox for sandbox in self.idle_sandboxes
                            if now - sandbox.created_at > self.config.idle_timeout][:max(0, surplus)]
        for sandbox in expired_active:
            logger.warning("[%s] Sandbox %s exceeded running timeout, disposing...", self.language, sandbox.short_id)
            self.dispose(sandbox)
        for sandbox in expired_idle:
            self.dispose(sandbox)

    def monitor(self):
        """Called periodically by the manager: timeouts, quarantine retry, replenishment."""
        self.check_ttls()
        self.retry_quarantined()
        self.replenish()

        self._monitor_counter += 1
        if self._monitor_counter >= 10:
            self._monitor_counter = 0
            stats = self.get_stats()
            if stats["quarantined"]:
                logger.error("[%s] %s sandbox(es) quarantined awaiting removal: %s", self.language,
                             stats["quarantined"], stats["quarantine"])
            if stats["utilization"] >= 90:
                logger.warning("[%s] HIGH LOAD - idle: %s, active: %s, total: %s/%s, utilization: %.1f%%",
                               self.language, stats['idle'], stats['active'],
                               stats['total'], stats['scale_limit'], stats["utilization"])
            elif stats['active'] > 0:
                logger.debug("[%s] STATS - idle: %s, active: %s, total: %s/%s, utilization: %.1f%%",
                             self.language, stats['idle'], stats['active'],
                             stats['total'], stats['scale_limit'], stats["utilization"])

    def get_stats(self) -> dict:
        """Counts per state, including quarantined containers and their errors."""
        with self.lock:
            total = self._tracked_count()
            active = len(self.active_sandboxes)
            return {
                "language": self.language.value,
                "idle": len(self.idle_sandboxes),
                "active": active,
                "closing": len(self.closing_sandboxes),
                "quarantined": len(self.quarantined_sandboxes),
                "quarantine": [
                    {"container_id": sandbox.short_id, "attempts": sandbox.disposal_attempts,
                     "exhausted": sandbox.disposal_attempts >= self.config.disposal_attempts,
                     "error": sandbox.last_disposal_error}
                    for sandbox in self.quarantined_sandboxes
                ],
                "total": total,
                "pool_size": self.config.pool_size,
                "scale_limit": self.config.scale_limit,
                "utilization": active / total * 100 if total else 0,
            }

    # ------------------------------------------------------------------ creation
    def _labels(self) -> Dict[str, str]:
        return {
            **self.owner.labels(),
            LABEL_VERSION: SANDBOX_VERSION,
            LABEL_LANGUAGE: self.language.value,
            LABEL_POOL_ID: self.pool_id,
            LABEL_CREATED_AT: datetime.now().isoformat(),
        }

    def _create_sandbox(self) -> SandboxContainer:
        """Create one container from the single Docker profile (gVisor when available)."""
        name = self._build_container_name()
        options = container_options(self.config.image, name, self._labels())
        container = None
        if self._gvisor_available:
            try:
                container = self.client.containers.run(runtime=GVISOR_RUNTIME, **options)
            except Exception as e:  # pylint: disable=broad-exception-caught
                if not is_missing_runtime_error(e):
                    raise
                logger.info("[%s] gVisor runtime not available, using the default runtime", self.language)
                self._gvisor_available = False
                self._remove_by_name(name)
        if container is None:
            container = self.client.containers.run(**options)
        logger.info("[%s] SANDBOX CREATED - %s (%s)", self.language, name, container.id[:12])
        sandbox = SandboxContainer(language=self.language, container_ref=container)
        sandbox.created_at = self._clock()
        return sandbox

    def _remove_by_name(self, name: str) -> None:
        """A failed runtime start may leave a created container holding the name."""
        try:
            self.client.containers.get(name).remove(force=True, v=True)
        except docker.errors.NotFound:
            pass
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("[%s] Could not remove partially created container %s", self.language, name)

    def _build_container_name(self) -> str:
        """Build deterministic container name: ag-sbx-{lang}-{pool8}-{seq4}"""
        self._sandbox_seq += 1
        return f"ag-sbx-{self.language.value}-{self.pool_id[:8]}-{self._sandbox_seq:04d}"

    # ------------------------------------------------------------------ shutdown
    def shutdown(self) -> int:
        """Stop handing out sandboxes and dispose every tracked one.

        Quarantined sandboxes get one more attempt. Returns how many remain
        quarantined; they carry this owner's labels, so the next manager on this
        host reclaims them once this process has exited.
        """
        with self.lock:
            self._closed = True
            pending = list(self.active_sandboxes) + list(self.idle_sandboxes)
        for sandbox in pending:
            try:
                self.dispose(sandbox)
            except ValueError:
                pass  # Disposed concurrently.
        self.retry_quarantined(final=True)
        with self.lock:
            remaining = len(self.quarantined_sandboxes) + len(self.closing_sandboxes)
        if remaining:
            logger.error("[%s] Pool shutdown left %s sandbox(es) unconfirmed; they remain labelled with owner %s",
                         self.language, remaining, self.owner.owner_id)
        else:
            logger.info("[%s] Pool shutdown complete.", self.language)
        return remaining
