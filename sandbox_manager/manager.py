"""Host-owned local sandbox manager.

The host constructs one manager, calls :meth:`SandboxManager.start` during its
startup and :meth:`SandboxManager.shutdown` during its shutdown. The library
installs no signal handlers, ``atexit`` hooks or process-global instances.

Lease API (shared with :class:`~sandbox_manager.remote_client.RemoteSandboxManager`)::

    sandbox = manager.acquire(Language.PYTHON)   # the caller now owns the lease
    ...prepare_workdir / inject_assets / run_command / extract_file...
    manager.dispose(sandbox)                     # idempotent, confirmed destruction
"""
import logging
import threading
from typing import Dict, Iterable, Optional

import docker

from sandbox_manager.errors import Disposal, SandboxCapacityError, SandboxCleanupError
from sandbox_manager.language_pool import LanguagePool
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.ownership import LABEL_OWNER, OwnerLease, ReclaimReport, reclaim_dead_owners
from sandbox_manager.sandbox_container import SandboxContainer

logger = logging.getLogger(__name__)


class SandboxManager:
    """Owns local language pools, their containers and their monitor thread."""

    def __init__(self, pool_configs: Iterable[SandboxPoolConfig], *, client: Optional[docker.DockerClient] = None,
                 lease_dir: Optional[str] = None, monitor_interval: float = 1.0):
        self.pool_configs = {config.language: config for config in pool_configs}
        if not self.pool_configs:
            raise ValueError("At least one sandbox pool configuration is required")
        self._client = client
        self._owns_client = client is None
        self.owner = OwnerLease(lease_dir)
        self.monitor_interval = monitor_interval
        self.language_pools: Dict[Language, LanguagePool] = {}
        self.reclaim_report: Optional[ReclaimReport] = None
        self._state = "new"
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    @property
    def owner_id(self) -> str:
        return self.owner.owner_id

    # ----- host lifetime -------------------------------------------------------------
    def start(self, *, monitor: bool = True) -> "SandboxManager":
        """Take ownership, reclaim provably dead owners, warm pools and start monitoring."""
        with self._state_lock:
            if self._state != "new":
                raise RuntimeError(f"SandboxManager cannot start from state '{self._state}'")
            self._state = "starting"
        try:
            if self._client is None:
                self._client = docker.from_env()
            self.owner.acquire()
            self.reclaim_report = reclaim_dead_owners(self._client, self.owner.lease_dir,
                                                      own_owner_id=self.owner_id)
            available = set((self._client.info().get("Runtimes") or {}).keys())
            for language, config in self.pool_configs.items():
                runtime = config.profile.resolve_runtime(available)
                self.language_pools[language] = LanguagePool(
                    language, config, self._client, owner_id=self.owner_id, runtime=runtime)
            logger.info("Sandbox manager %s started (runtimes: %s)", self.owner_id[:8],
                        sorted({pool.runtime for pool in self.language_pools.values()}))
            for pool in self.language_pools.values():
                pool.replenish()
        except BaseException:
            self._state = "started"
            self.shutdown(raise_on_pending=False)
            raise
        self._state = "started"
        if monitor:
            self._monitor_thread = threading.Thread(target=self._monitor, name="sandbox-monitor", daemon=True)
            self._monitor_thread.start()
        return self

    def shutdown(self, *, raise_on_pending: bool = True) -> None:
        """Stop monitoring and destroy every owned container. Safe to repeat.

        Unconfirmed destruction keeps the owner's lease file after the lock is
        released, so the next host start reclaims the remainder, and raises
        ``SandboxCleanupError`` for host logging.
        """
        with self._state_lock:
            if self._state == "new":
                self._state = "stopped"
                return
            self._state = "stopped"
        self._stop.set()
        if self._monitor_thread is not None and self._monitor_thread is not threading.current_thread():
            self._monitor_thread.join(timeout=30)
        pending = 0
        for language, pool in self.language_pools.items():
            try:
                pending += pool.shutdown()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Error shutting down the %s pool", language.value)
                pending += 1
        pending += self._sweep_untracked()
        self.owner.release(resources_remain=pending > 0)
        if self._owns_client and self._client is not None and pending == 0:
            self._client.close()
        if pending:
            logger.error("Sandbox manager %s stopped with %d unconfirmed container cleanup(s); "
                         "the next host start reclaims them", self.owner_id[:8], pending)
            if raise_on_pending:
                raise SandboxCleanupError(f"{pending} sandbox container(s) could not be destroyed at shutdown")

    def _sweep_untracked(self) -> int:
        """Remove containers carrying this owner's label that no record tracks."""
        if self._client is None or not self.owner.held:
            return 0
        try:
            leftovers = self._client.containers.list(all=True, filters={"label": f"{LABEL_OWNER}={self.owner_id}"})
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Could not list this owner's containers at shutdown")
            return 1
        failed = 0
        for container in leftovers:
            try:
                container.remove(force=True, v=True)
            except docker.errors.NotFound:
                pass
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Could not remove untracked sandbox container %s", container.id[:12])
                failed += 1
        return failed

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(raise_on_pending=exc_type is None)
        return False

    def _monitor(self):
        while not self._stop.wait(self.monitor_interval):
            for pool in self.language_pools.values():
                try:
                    pool.monitor()
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Error monitoring the %s pool", pool.language.value)

    # ----- leases --------------------------------------------------------------------
    def _pool(self, language: Language) -> LanguagePool:
        if self._state != "started":
            raise SandboxCapacityError("The sandbox manager is not running")
        try:
            return self.language_pools[language]
        except KeyError:
            raise SandboxCapacityError(f"No sandbox pool is configured for {language.value}") from None

    def acquire(self, language: Language) -> SandboxContainer:
        """Lease a sandbox. The caller must call :meth:`dispose` exactly when finished."""
        return self._pool(language).acquire()

    def dispose(self, sandbox: SandboxContainer) -> Disposal:
        """Destroy a leased sandbox. Repeating it is safe; see :class:`Disposal`.

        Raises ``SandboxCleanupError`` while Docker has not confirmed removal; the
        record stays owned by the pool and the monitor retries it.
        """
        pool = self.language_pools.get(sandbox.language)
        if pool is None:
            raise ValueError("Sandbox does not belong to this manager")
        result = pool.dispose(sandbox)
        pool.replenish()  # keep pool_size warm for the next lease
        return result

    def lease_seconds(self, language: Language) -> int:
        """Maximum lifetime of one lease (the pool's ``running_timeout``)."""
        return self.pool_configs[language].running_timeout

    # ----- observability -------------------------------------------------------------
    def get_pool_stats(self) -> dict:
        return {language.value: pool.get_stats() for language, pool in self.language_pools.items()}

    def cleanup_problems(self) -> list:
        return [problem for pool in self.language_pools.values() for problem in pool.cleanup_problems()]
