"""Local sandbox manager: per-language pools under one owner lease.

The host that constructs a :class:`SandboxManager` owns its lifetime and must
call :meth:`SandboxManager.shutdown` (for example in a ``finally`` block or an
application lifespan). The library installs no signal handlers or ``atexit``
hooks; hosts keep their own signal behaviour.
"""
import logging
import threading
from contextlib import contextmanager
from typing import Dict, Iterable, Optional

import docker

from sandbox_manager.language_pool import LanguagePool
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import DisposalStatus, Language
from sandbox_manager.ownership import OwnerIdentity, reclaim_dead_owners
from sandbox_manager.sandbox_container import SandboxContainer

logger = logging.getLogger(__name__)


class SandboxManager:
    """Owns the language pools, their monitor thread and this process's owner lease."""

    def __init__(self, pool_configs: Iterable[SandboxPoolConfig], client: Optional[docker.DockerClient] = None,
                 *, owner: Optional[OwnerIdentity] = None, reclaim_orphans: bool = True,
                 monitor_interval: float = 1.0):
        configs = list(pool_configs)
        if not configs:
            raise ValueError("pool_configs must not be empty")
        for config in configs:
            if not isinstance(config.language, Language):
                raise ValueError(f"Unsupported language: {config.language}")
        self._owns_client = client is None
        self.client = client or docker.from_env()
        self.owner = owner or OwnerIdentity.current()
        if reclaim_orphans:
            reclaim_dead_owners(self.client, self.owner)
        self.language_pools: Dict[Language, LanguagePool] = {
            config.language: LanguagePool(config.language, config, self.client, self.owner)
            for config in configs
        }
        self._stop = threading.Event()
        self._shutdown_lock = threading.Lock()
        self._shut_down = False
        self._monitor_interval = monitor_interval
        for pool in self.language_pools.values():
            pool.replenish()
        self.monitor_thread = threading.Thread(target=self._pool_monitor, name="sandbox-pool-monitor",
                                               daemon=True)
        self.monitor_thread.start()

    def _pool(self, lang: Language) -> LanguagePool:
        pool = self.language_pools.get(lang)
        if pool is None:
            raise ValueError(f"Unsupported language: {lang}")
        return pool

    def get_sandbox(self, lang: Language) -> SandboxContainer:
        """Acquire a fresh sandbox; the caller must :meth:`dispose` it."""
        return self._pool(lang).acquire()

    def dispose(self, sandbox: SandboxContainer) -> DisposalStatus:
        """Destroy a used sandbox. Idempotent; see :class:`DisposalStatus`."""
        return self._pool(sandbox.language).dispose(sandbox)

    @contextmanager
    def acquire_sandbox(self, lang: Language):
        """Acquire a sandbox and dispose it when the block exits."""
        sandbox = self.get_sandbox(lang)
        try:
            yield sandbox
        finally:
            self.dispose(sandbox)

    def shutdown(self) -> None:
        """Stop the monitor, then dispose every container. Safe to call repeatedly."""
        with self._shutdown_lock:
            if self._shut_down:
                return
            self._shut_down = True
        logger.info("[SandboxManager] Initiating shutdown (owner %s)...", self.owner.owner_id[:8])
        self._stop.set()
        if self.monitor_thread is not threading.current_thread():
            self.monitor_thread.join(timeout=max(30.0, self._monitor_interval * 5))
            if self.monitor_thread.is_alive():
                logger.error("[SandboxManager] Pool monitor did not stop within the shutdown timeout")
        for language, pool in self.language_pools.items():
            try:
                pool.shutdown()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("[SandboxManager] Error shutting down %s pool", language)
        if self._owns_client:
            self.client.close()
        logger.info("[SandboxManager] Shutdown complete")

    def get_pool_stats(self) -> dict:
        """Per-language pool statistics, including quarantined containers."""
        return {language.value: pool.get_stats() for language, pool in self.language_pools.items()}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def _pool_monitor(self):
        while not self._stop.wait(self._monitor_interval):
            for pool in self.language_pools.values():
                if self._stop.is_set():
                    return
                try:
                    pool.monitor()
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Error monitoring pool for language %s", pool.language)
