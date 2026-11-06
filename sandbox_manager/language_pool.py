"""One language's sandbox pool under the host-wide sandbox budget.

Lifecycle: idle -> active -> closing -> (disposed | quarantined). A used
sandbox is never reused. :meth:`LanguagePool.dispose` is the only way a tracked
sandbox leaves the pool, and it forgets a sandbox only after Docker confirms
removal (``NotFound`` counts as confirmation). When Docker fails to remove it,
the sandbox is quarantined: it stays tracked, keeps its budget slot, is reported
in :meth:`get_stats`, and the monitor retries its removal a bounded number of
times with backoff.

Every pool of one manager shares a :class:`SandboxBudget` of ``N`` slots and its
lock. A slot is held from the moment an acquisition (or warm-up) starts creating
a container until Docker confirms the container's removal, so at every instant
``creating + active + closing + quarantined <= N``. Warm idle containers (at most
``pool_size`` per language) hold no slot; taking one takes a slot. Acquisition
waits in FIFO order for a slot up to the caller's ``wait_seconds`` and raises
:class:`~sandbox_manager.errors.SandboxCapacityTimeout` on expiry. Docker
create and remove calls never run under the lock.
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
from sandbox_manager.errors import SandboxCapacityTimeout, SandboxLifetimeExceeded
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

# Slack for container start-up in an idle container's outer bound (see _outer_bound).
CREATION_SLACK_SECONDS = 60
DISPOSAL_BACKOFF_SECONDS = 1.0
DISPOSAL_BACKOFF_MAX_SECONDS = 60.0

logger = logging.getLogger(__name__)


class SandboxUnavailableError(ValueError):
    """The pool cannot hand out a sandbox (shut down, or container creation failed)."""


class SandboxBudget:
    """``limit`` execution slots shared by every pool of one host, with FIFO waiters.

    ``condition`` is also each pool's lock, so pool state and slot accounting
    change together. It is only held for bookkeeping, never for Docker calls.
    """

    def __init__(self, limit: int):
        if limit < 1:
            raise ValueError("The sandbox budget must allow at least one sandbox")
        self.limit = limit
        self.held = 0
        self.condition = threading.Condition()
        self._waiters: deque = deque()

    def take(self, wait_seconds: float, closed: Callable[[], bool]) -> None:
        """Take one slot, waiting in FIFO order. Call with ``condition`` held."""
        deadline = time.monotonic() + max(0.0, wait_seconds)
        ticket = object()
        self._waiters.append(ticket)
        self.condition.notify_all()  # Joining the queue is a state change others may wait on.
        try:
            while True:
                if closed():
                    raise SandboxUnavailableError("The sandbox pool is shut down")
                if self._waiters[0] is ticket and self.held < self.limit:
                    self.held += 1
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SandboxCapacityTimeout(
                        f"No sandbox slot became free within {wait_seconds:g}s (max_sandboxes: {self.limit})")
                self.condition.wait(remaining)
        finally:
            self._waiters.remove(ticket)
            self.condition.notify_all()  # The next waiter may now be first in line.

    def try_take_unwaited(self) -> bool:
        """Take a slot only when nobody is waiting (warm-up yields to acquisitions)."""
        if self._waiters or self.held >= self.limit:
            return False
        self.held += 1
        return True

    def release(self) -> None:
        """Return one slot. Call with ``condition`` held."""
        self.held -= 1
        self.condition.notify_all()

    def stats(self) -> dict:
        """The limit, slots held and acquisitions waiting."""
        with self.condition:
            return {"max_sandboxes": self.limit, "held": self.held, "waiting": len(self._waiters)}


class LanguagePool:
    """Warm containers for one language, each used once and then disposed."""

    def __init__(self, language: Language, config: SandboxPoolConfig, client: DockerClient = None,
                 owner: Optional[OwnerIdentity] = None, clock: Callable[[], float] = time.monotonic, *,
                 budget: SandboxBudget):
        self.language = language
        self.config = config
        self.client = client
        self.owner = owner or OwnerIdentity.current()
        self.pool_id = str(uuid.uuid4())
        self.budget = budget
        self._sandbox_seq = 0
        self._clock = clock
        self._gvisor_available = True
        self._closed = False
        self._creating = 0

        self.idle_sandboxes: deque[SandboxContainer] = deque()
        self.active_sandboxes: Set[SandboxContainer] = set()
        self.closing_sandboxes: Set[SandboxContainer] = set()
        self.quarantined_sandboxes: Set[SandboxContainer] = set()
        self._monitor_counter = 0

        # The budget's lock: shared by the host's pools; Docker calls always happen outside it.
        self.lock = budget.condition

        logger.info("[%s] POOL INITIALIZED - pool_size: %s, max_sandboxes: %s, pool_id: %s, owner: %s",
                    language, config.pool_size, budget.limit, self.pool_id[:8], self.owner.owner_id[:8])

    # ------------------------------------------------------------------ capacity
    def _tracked_count(self) -> int:
        """Every container this pool is responsible for, including unconfirmed removals."""
        return (len(self.idle_sandboxes) + len(self.active_sandboxes)
                + len(self.closing_sandboxes) + len(self.quarantined_sandboxes))

    def acquire(self, wait_seconds: float = 0.0, lifetime: Optional[float] = None) -> SandboxContainer:
        """Take a budget slot (waiting up to ``wait_seconds``), then an idle sandbox or a new one.

        The sandbox stops by itself ``lifetime`` seconds after the grant
        (default and maximum: ``running_timeout``), whether or not its owner is
        still alive. Raises :class:`SandboxLifetimeExceeded` before waiting when
        ``lifetime`` exceeds ``running_timeout``, :class:`SandboxCapacityTimeout`
        when no slot frees up in time and :class:`SandboxUnavailableError` when
        the pool is shut down or creation fails.
        """
        lifetime = self.config.running_timeout if lifetime is None else lifetime
        if not 0 < lifetime <= self.config.running_timeout:
            raise SandboxLifetimeExceeded(f"A sandbox lifetime of {lifetime:g}s exceeds this host's "
                                          f"running_timeout of {self.config.running_timeout}s")
        with self.lock:
            self.budget.take(wait_seconds, lambda: self._closed)
            sandbox = self._take_idle()
            if sandbox is None:
                self._creating += 1
                name = self._build_container_name()
        if sandbox is None:
            sandbox = self._create_outside_lock(name, keep_slot=True)
            logger.info("[%s] CREATED for acquisition - sandbox_id: %s", self.language, sandbox.short_id)
        try:
            sandbox.arm_lifetime(lifetime)
        except Exception as exc:
            self.dispose(sandbox)
            raise SandboxUnavailableError(f"Failed to start a sandbox for language {self.language.value}") from exc
        return sandbox

    def _take_idle(self) -> Optional[SandboxContainer]:
        """An idle sandbox young enough to outlive any grant (call with the lock held).

        Older ones stay idle until the monitor disposes them (``check_ttls``).
        """
        now = self._clock()
        for sandbox in self.idle_sandboxes:
            if now - sandbox.created_at < self.config.running_timeout:
                self.idle_sandboxes.remove(sandbox)
                sandbox.holds_slot = True
                sandbox.activate(now)
                self.active_sandboxes.add(sandbox)
                logger.info("[%s] ACQUIRED from idle pool - sandbox_id: %s", self.language, sandbox.short_id)
                return sandbox
        return None

    def _outer_bound(self) -> int:
        """PID 1's own lifetime: an idle container is granted before it is ``running_timeout``
        old, for at most ``running_timeout``, so it never needs longer; an orphaned idle one stops by then."""
        return 2 * self.config.running_timeout + CREATION_SLACK_SECONDS

    def _create_outside_lock(self, name: str, *, keep_slot: bool) -> SandboxContainer:
        """Create a reserved container; a failure or a shutdown meanwhile releases its slot."""
        try:
            sandbox = self._create_sandbox(name)
        except Exception as exc:
            with self.lock:
                self._creating -= 1
                self.budget.release()
            logger.exception("[%s] SANDBOX CREATION FAILED - Error: %s", self.language, exc)
            raise SandboxUnavailableError(f"Failed to create sandbox for language {self.language.value}") from exc
        sandbox.holds_slot = True
        with self.lock:
            if not self._closed:
                self._creating -= 1
                if keep_slot:
                    sandbox.activate(self._clock())
                    self.active_sandboxes.add(sandbox)
                else:
                    sandbox.holds_slot = False
                    self.budget.release()
                    self.idle_sandboxes.append(sandbox)
                return sandbox
            # Shut down while Docker was creating it: remove it before shutdown completes.
            sandbox.state = SandboxState.CLOSING
            self.closing_sandboxes.add(sandbox)
        try:
            self._remove_container(sandbox)
        finally:
            with self.lock:
                self._creating -= 1
                self.lock.notify_all()
        raise SandboxUnavailableError(f"Sandbox pool for {self.language.value} is shut down")

    def replenish(self):
        """Warm up to ``pool_size`` idle sandboxes using only slots no acquisition is waiting for."""
        while True:
            with self.lock:
                if (self._closed or len(self.idle_sandboxes) + self._creating >= self.config.pool_size
                        or not self.budget.try_take_unwaited()):
                    return
                self._creating += 1
                name = self._build_container_name()
            try:
                sandbox = self._create_outside_lock(name, keep_slot=False)
            except SandboxUnavailableError:
                return  # Logged; the monitor tries again on its next pass.
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
                if sandbox.holds_slot:
                    sandbox.holds_slot = False
                    self.budget.release()
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
        """Dispose active sandboxes past their lifetime (measured from the grant; the
        container has stopped itself) and idle ones too old to be granted."""
        now = self._clock()
        with self.lock:
            expired = [sandbox for sandbox in self.active_sandboxes
                       if now - (sandbox.activated_at or sandbox.created_at)
                       > (sandbox.lifetime or self.config.running_timeout)]
            stale = [sandbox for sandbox in self.idle_sandboxes
                     if now - sandbox.created_at >= self.config.running_timeout]
        for sandbox in expired:
            logger.warning("[%s] Sandbox %s reached its lifetime, disposing...", self.language, sandbox.short_id)
            self.dispose(sandbox)
        for sandbox in stale:
            try:
                self.dispose(sandbox)
            except ValueError:
                pass  # taken or disposed meanwhile

    def monitor(self):
        """Called periodically by the manager: running timeouts, quarantine retry, warm-up."""
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
            if stats["active"]:
                logger.debug("[%s] STATS - idle: %s, creating: %s, active: %s, closing: %s",
                             self.language, stats["idle"], stats["creating"], stats["active"], stats["closing"])

    def get_stats(self) -> dict:
        """Counts per state, including quarantined containers and their errors."""
        with self.lock:
            return {
                "language": self.language.value,
                "idle": len(self.idle_sandboxes),
                "creating": self._creating,
                "active": len(self.active_sandboxes),
                "closing": len(self.closing_sandboxes),
                "quarantined": len(self.quarantined_sandboxes),
                "quarantine": [
                    {"container_id": sandbox.short_id, "attempts": sandbox.disposal_attempts,
                     "exhausted": sandbox.disposal_attempts >= self.config.disposal_attempts,
                     "error": sandbox.last_disposal_error}
                    for sandbox in self.quarantined_sandboxes
                ],
                "total": self._tracked_count(),
                "pool_size": self.config.pool_size,
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

    def _create_sandbox(self, name: str) -> SandboxContainer:
        """Create one container from the single Docker profile (gVisor when available).

        Runs outside the lock. Concurrent creators may each discover a missing
        gVisor runtime; each removes only its own uniquely named attempt.
        """
        options = container_options(self.config.image, name, self._labels(), self._outer_bound())
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
        """Build deterministic container name: ag-sbx-{lang}-{pool8}-{seq4}. Call with the lock held."""
        self._sandbox_seq += 1
        return f"ag-sbx-{self.language.value}-{self.pool_id[:8]}-{self._sandbox_seq:04d}"

    # ------------------------------------------------------------------ shutdown
    def close(self) -> None:
        """Refuse new acquisitions and wake waiting ones (they raise SandboxUnavailableError)."""
        with self.lock:
            self._closed = True
            self.lock.notify_all()

    def shutdown(self) -> int:
        """Stop handing out sandboxes and dispose every tracked one.

        Waiting acquisitions fail with :class:`SandboxUnavailableError`; an
        in-flight creation removes its container before this returns.
        Quarantined sandboxes get one more attempt. Returns how many remain
        quarantined; they carry this owner's labels, so the next manager on this
        host reclaims them once this process has exited.
        """
        self.close()
        with self.lock:
            pending = list(self.active_sandboxes) + list(self.idle_sandboxes)
        for sandbox in pending:
            try:
                self.dispose(sandbox)
            except ValueError:
                pass  # Disposed concurrently.
        with self.lock:
            while self._creating:
                self.lock.wait()
        self.retry_quarantined(final=True)
        with self.lock:
            remaining = len(self.quarantined_sandboxes) + len(self.closing_sandboxes)
        if remaining:
            logger.error("[%s] Pool shutdown left %s sandbox(es) unconfirmed; they remain labelled with owner %s",
                         self.language, remaining, self.owner.owner_id)
        else:
            logger.info("[%s] Pool shutdown complete.", self.language)
        return remaining
