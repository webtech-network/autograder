import atexit
import signal
import threading
import time
from typing import Dict, List, Optional
import docker
from sandbox_manager.language_pool import LanguagePool, LABEL_APP
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.sandbox_container import SandboxContainer

_manager_instance: Optional['SandboxManager'] = None
_client = docker.from_env()

def initialize_sandbox_manager(pool_configs: List[SandboxPoolConfig]) -> 'SandboxManager':
    """
    Should be called upon application startup.
    Cleans up orphaned containers from previous runs and initializes pools.
    """
    global _manager_instance

    for config in pool_configs:
        if config.language not in Language:
            raise ValueError(f"Unsupported language: {config.language}")

    # Clean up orphaned containers before initializing new pools
    print("[SandboxManager] Cleaning up orphaned containers from previous runs...")
    _cleanup_orphaned_containers(_client)

    language_pools = {config.language: LanguagePool(config.language, config, _client) for config in pool_configs}
    _manager_instance = SandboxManager(language_pools)

    # Register cleanup handlers
    _register_shutdown_handlers(_manager_instance)

    return _manager_instance

def get_sandbox_manager() -> 'SandboxManager':
    if _manager_instance is None:
        raise ValueError("SandboxManager has not been initialized. Call initialize_sandbox_manager() first.")
    return _manager_instance


def _cleanup_orphaned_containers(client: docker.DockerClient):
    """
    Find and destroy all orphaned sandbox containers from previous runs.
    Identifies containers by the autograder.sandbox.app label.
    """
    try:
        # Find all containers with our app label
        orphaned_containers = client.containers.list(
            all=True,
            filters={"label": f"{LABEL_APP}=autograder-sandbox"}
        )

        if orphaned_containers:
            print(f"[SandboxManager] Found {len(orphaned_containers)} orphaned container(s)")
            for container in orphaned_containers:
                try:
                    print(f"[SandboxManager] Removing orphaned container {container.id[:12]}...")
                    container.remove(force=True)
                except Exception as e:
                    print(f"[SandboxManager] Failed to remove orphaned container {container.id[:12]}: {e}")
            print(f"[SandboxManager] Orphan cleanup complete")
        else:
            print("[SandboxManager] No orphaned containers found")
    except Exception as e:
        print(f"[SandboxManager] Error during orphan cleanup: {e}")


def _register_shutdown_handlers(manager: 'SandboxManager'):
    """
    Register signal handlers and atexit cleanup to ensure containers are destroyed
    even on unexpected termination.
    """
    def shutdown_handler(signum=None, frame=None):
        print(f"\n[SandboxManager] Received shutdown signal, cleaning up...")
        manager.shutdown()

    # Register for common termination signals
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Register atexit handler as last resort
    atexit.register(shutdown_handler)

class SandboxManager:
    def __init__(self, language_pools: Dict[Language, LanguagePool]):
        self.language_pools = language_pools
        self._shutdown_in_progress = False
        for pool in self.language_pools.values():
            pool.replenish() # Initial creation of sandboxes in each pool
        self.monitor_thread = threading.Thread(target=self.__pool_monitor, daemon=True)
        self.monitor_thread.start()

    def get_sandbox(self, lang: Language) -> SandboxContainer:
        if lang in self.language_pools:
            return self.language_pools[lang].acquire()
        else:
            raise ValueError(f"Unsupported language: {lang}")

    def release_sandbox(self, lang: Language, sandbox: SandboxContainer):
        if lang in self.language_pools:
            self.language_pools[lang].release(sandbox)

    def acquire_sandbox(self, lang: Language):
        """
        Context manager for safe sandbox acquisition and guaranteed release.

        Usage:
            manager = get_sandbox_manager()
            with manager.acquire_sandbox(Language.PYTHON) as sandbox:
                result = sandbox.run_command("python script.py")
            # Sandbox is automatically released even if an exception occurs
        """
        from contextlib import contextmanager

        @contextmanager
        def _sandbox_context():
            sandbox = self.get_sandbox(lang)
            try:
                yield sandbox
            finally:
                self.release_sandbox(lang, sandbox)

        return _sandbox_context()

    def shutdown(self):
        """
        Gracefully shutdown all pools and destroy all containers.
        Safe to call multiple times.
        """
        if self._shutdown_in_progress:
            return

        self._shutdown_in_progress = True
        print("[SandboxManager] Initiating shutdown...")

        # Destroy all containers in all pools
        for language, pool in self.language_pools.items():
            try:
                pool.shutdown()
            except Exception as e:
                print(f"[SandboxManager] Error shutting down {language} pool: {e}")

        print("[SandboxManager] Shutdown complete")

    def get_pool_stats(self) -> dict:
        """
        Get statistics for all language pools.
        Useful for monitoring and debugging scaling behavior.
        """
        stats = {}
        for language, pool in self.language_pools.items():
            stats[language.value] = pool.get_stats()
        return stats

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.shutdown()
        return False  # Don't suppress exceptions

    def __pool_monitor(self):
        while not self._shutdown_in_progress:
            for pool in self.language_pools.values():
                try:
                    pool.monitor()
                except Exception as e:
                    print(f"Error monitoring pool for language {pool.language}: {e}")
            time.sleep(1)







