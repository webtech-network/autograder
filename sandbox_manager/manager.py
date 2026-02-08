import threading
import time
from typing import Dict, List
import docker
from sandbox_manager.language_pool import LanguagePool
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.sandbox_container import SandboxContainer

client = docker.from_env()

def get_sandbox_manager(pool_configs: List[SandboxPoolConfig]) -> 'SandboxManager':
    for config in pool_configs:
        if config.language not in Language:
            raise ValueError(f"Unsupported language: {config.language}")
    language_pools = {config.language:LanguagePool(config.language, config, client) for config in pool_configs}
    return SandboxManager(language_pools)

class SandboxManager:
    def __init__(self, language_pools: Dict[Language,LanguagePool]):
        self.language_pools = language_pools
        for pool in self.language_pools.values():
            pool.replenish() # Initial creation of sandboxes in each pool
        self.monitor_thread = threading.Thread(target=self.__pool_monitor)
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







