"""Local sandbox manager: per-language pools under one owner lease and one sandbox budget.

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

from sandbox_manager.docker_profile import GVISOR_RUNTIME, RUNTIMES
from sandbox_manager.errors import IsolationRuntimeError, RuntimeImageError, RuntimeUnavailableError
from sandbox_manager.language_pool import LanguagePool, SandboxBudget
from sandbox_manager.models.pool_config import SandboxHostConfig, SandboxPoolConfig
from sandbox_manager.models.sandbox_models import DisposalStatus
from autograder.models.language import Language
from sandbox_manager.ownership import OwnerIdentity, reclaim_dead_owners
from sandbox_manager.sandbox_container import SandboxContainer

logger = logging.getLogger(__name__)

#: Image label listing the comma-separated language identifiers an image serves.
RUNTIME_LANGUAGES_LABEL = "autograder.runtime.languages"


def verify_runtime_images(client: docker.DockerClient, configs: Iterable[SandboxPoolConfig]) -> None:
    """Require each configured image to be present locally and to declare its language.

    Nothing is pulled: a missing reference is an operator error with one fix.
    Other Docker errors propagate unchanged.
    """
    for config in configs:
        try:
            image = client.images.get(config.image)
        except docker.errors.ImageNotFound:
            raise RuntimeImageError(
                f"Sandbox image '{config.image}' for the '{config.language.value}' runtime is not on this "
                f"Docker host. Run `docker pull {config.image}` (or `make sandbox-build-all` for the images "
                f"of this checkout), or change `runtimes:` in the sandbox configuration.") from None
        declared = [item.strip() for item in (image.labels or {}).get(RUNTIME_LANGUAGES_LABEL, "").split(",")]
        if config.language.value not in declared:
            raise RuntimeImageError(
                f"Sandbox image '{config.image}' does not declare the '{config.language.value}' runtime "
                f"(label {RUNTIME_LANGUAGES_LABEL}={','.join(filter(None, declared)) or '<missing>'}). "
                "Map the language to the image built for it in `runtimes:`.")


def verify_isolation_runtime(client: docker.DockerClient, runtime: str) -> None:
    """Require the Docker daemon to offer the configured OCI runtime, and log the decision.

    The runtime is the host's explicit choice; it is never replaced by another one.
    """
    if runtime not in RUNTIMES:
        raise IsolationRuntimeError(f"Unknown sandbox runtime '{runtime}'; set general.runtime to one of "
                                    f"{', '.join(RUNTIMES)}")
    offered = client.info().get("Runtimes") or {}
    if runtime not in offered:
        raise IsolationRuntimeError(
            f"The sandbox runtime '{runtime}' (general.runtime) is not offered by this Docker daemon "
            f"(it offers: {', '.join(sorted(offered)) or 'none'}). Install and register it, or choose another "
            "runtime explicitly; sandboxes never fall back to a different runtime.")
    if runtime == GVISOR_RUNTIME:
        logger.info("[SandboxManager] Sandboxes run under gVisor (runsc), as configured by general.runtime")
    else:
        logger.warning("[SandboxManager] Sandboxes run under %s, as configured by general.runtime: submissions "
                       "share the host kernel without gVisor's isolation", runtime)


class SandboxManager:
    """Owns the language pools, their shared budget, the monitor thread and this process's owner lease.

    ``max_sandboxes`` (N) bounds creating + active + closing + quarantined
    sandboxes across every language; acquisitions beyond it wait. ``runtime``
    is the OCI runtime every sandbox uses (``runsc`` or ``runc``), the host's
    explicit decision: the manager refuses to start when the daemon lacks it.
    """

    def __init__(self, pool_configs: Iterable[SandboxPoolConfig], client: Optional[docker.DockerClient] = None,
                 *, max_sandboxes: int, runtime: str, owner: Optional[OwnerIdentity] = None,
                 reclaim_orphans: bool = True, monitor_interval: float = 1.0):
        configs = list(pool_configs)
        if not configs:
            raise ValueError("pool_configs must not be empty")
        for config in configs:
            if not isinstance(config.language, Language):
                raise ValueError(f"Unsupported language: {config.language}")
        self.budget = SandboxBudget(max_sandboxes)
        self._owns_client = client is None
        self.client = client or docker.from_env()
        try:
            verify_isolation_runtime(self.client, runtime)
            verify_runtime_images(self.client, configs)
        except Exception:
            if self._owns_client:
                self.client.close()
            raise
        self.runtime = runtime
        self.owner = owner or OwnerIdentity.current()
        if reclaim_orphans:
            reclaim_dead_owners(self.client, self.owner)
        self.language_pools: Dict[Language, LanguagePool] = {
            config.language: LanguagePool(config.language, config, self.client, self.owner, budget=self.budget,
                                          runtime=runtime)
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

    @classmethod
    def from_config(cls, config: SandboxHostConfig, client: Optional[docker.DockerClient] = None,
                    **options) -> "SandboxManager":
        """A manager for a loaded ``sandbox_config.yml``."""
        return cls(config.pools, client, max_sandboxes=config.max_sandboxes, runtime=config.runtime, **options)

    def _pool(self, lang: Language) -> LanguagePool:
        pool = self.language_pools.get(lang)
        if pool is None:
            raise RuntimeUnavailableError(f"No sandbox runtime is configured for {lang.value}")
        return pool

    def get_sandbox(self, lang: Language, wait_seconds: float = 0.0) -> SandboxContainer:
        """Acquire a fresh sandbox; the caller must :meth:`dispose` it.

        Waits up to ``wait_seconds`` for a budget slot, then raises
        :class:`~sandbox_manager.errors.SandboxCapacityTimeout`.
        """
        return self._pool(lang).acquire(wait_seconds)

    def dispose(self, sandbox: SandboxContainer) -> DisposalStatus:
        """Destroy a used sandbox. Idempotent; see :class:`DisposalStatus`."""
        pool = self.language_pools.get(sandbox.language)
        if pool is None:
            raise ValueError("Sandbox does not belong to this manager")
        return pool.dispose(sandbox)

    @contextmanager
    def acquire_sandbox(self, lang: Language, wait_seconds: float = 0.0):
        """Acquire a sandbox and dispose it when the block exits."""
        sandbox = self.get_sandbox(lang, wait_seconds)
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
        for pool in self.language_pools.values():
            pool.close()  # No pool may take slots another pool's shutdown frees.
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

    def get_budget_stats(self) -> dict:
        """The host budget: ``max_sandboxes``, slots ``held`` and acquisitions ``waiting``."""
        return self.budget.stats()

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
