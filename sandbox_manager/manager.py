import threading
import time
from typing import Dict, List, Optional
import docker
from sandbox_manager.language_pool import LanguagePool
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.sandbox_container import SandboxContainer

_manager_instance: Optional['SandboxManager'] = None
_client = docker.from_env()

def initialize_sandbox_manager(pool_configs: List[SandboxPoolConfig]) -> 'SandboxManager':
    """
    Should be called upon application startup
    """
    global _manager_instance

    for config in pool_configs:
        if config.language not in Language:
            raise ValueError(f"Unsupported language: {config.language}")
    language_pools = {config.language:LanguagePool(config.language, config, _client) for config in pool_configs}
    _manager_instance = SandboxManager(language_pools)
    return _manager_instance

def get_sandbox_manager() -> 'SandboxManager':
    if _manager_instance is None:
        raise ValueError("SandboxManager has not been initialized. Call initialize_sandbox_manager() first.")
    return _manager_instance

class SandboxManager:
    def __init__(self, language_pools: Dict[Language,LanguagePool]):
        self.language_pools = language_pools
        for pool in self.language_pools.values():
            pool.replenish() # Initial creation of sandboxes in each pool
        self.monitor_thread = threading.Thread(target=self.__pool_monitor, daemon=True)
        self.monitor_thread.start()

    def get_sandbox(self, lang: Language) -> SandboxContainer:
        if lang in self.language_pools:
            return self.language_pools[lang].acquire()
        else:
            raise ValueError(f"Unsupported language: {lang}")

    def release_sandbox(self, lang: Language , sandbox: SandboxContainer):
        if lang in self.language_pools:
            self.language_pools[lang].release(sandbox)


    def __pool_monitor(self):
        while True:
            for pool in self.language_pools.values():
                try:
                    pool.monitor()
                except Exception as e:
                    print(f"Error monitoring pool for language {pool.language}: {e}")
            time.sleep(1)







