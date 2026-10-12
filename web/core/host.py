"""Construct one web host with isolated database, providers and worker state."""
import asyncio

from autograder import describe_templates
from web.core.config import Settings
from web.database.session import create_database, init_db
from web.service.worker import DurableWorker


class BuiltinCatalog:
    def get_all_templates_info(self):
        return describe_templates().templates

    def get_template_info(self, name):
        for template in self.get_all_templates_info():
            if template.identifier == name:
                return template
        raise KeyError(f"Template '{name}' not found")


class WebHost:
    def __init__(self, settings=None, *, session_factory=None, capabilities=None,
                 resource_owner=None, evaluator=None, start_workers=True):
        self.settings = settings or Settings()
        self.engine = None
        if session_factory is None:
            self.engine, session_factory = create_database(
                self.settings.DATABASE_URL, echo=self.settings.DATABASE_ECHO,
                pool_size=self.settings.DATABASE_POOL_SIZE, max_overflow=self.settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=self.settings.DATABASE_POOL_TIMEOUT, pool_recycle=self.settings.DATABASE_POOL_RECYCLE,
            )
        self.sessions = session_factory
        self.resource_owner = resource_owner
        if capabilities is None:
            from execution_host.docker import DockerHost
            self.resource_owner = DockerHost(
                mode=self.settings.SANDBOX_MODE, api_url=self.settings.SANDBOX_API_URL,
                config_file=self.settings.SANDBOX_CONFIG_FILE,
            )
            capabilities = self.resource_owner.capabilities
        self.capabilities = capabilities
        self.templates = BuiltinCatalog()
        self.start_workers = start_workers
        worker_args = {"evaluator": evaluator} if evaluator is not None else {}
        self.worker = DurableWorker(self.sessions, self.settings, self.capabilities, **worker_args)
        self.ready = False
        self.execution_tasks = set()
        self._closing = None

    async def start(self):
        if self.engine is not None:
            await init_db(self.engine)
        self.ready = True
        if self.start_workers:
            self.worker.start()

    async def close(self):
        """Drain all owned execution, including detached deliberate-run threads."""
        self.ready = False
        self.worker.stopping.set()
        if self._closing is None:
            self._closing = asyncio.create_task(self._drain_and_close())
        try:
            await asyncio.shield(self._closing)
        except asyncio.CancelledError:
            await asyncio.shield(self._closing)
            raise

    async def _drain_and_close(self):
        await self.worker.stop()
        if self.execution_tasks:
            await asyncio.gather(*self.execution_tasks, return_exceptions=True)
        # Provider resources cannot close while any execution thread owns them.
        try:
            if self.resource_owner is not None:
                self.resource_owner.close()
        finally:
            if self.engine is not None:
                await self.engine.dispose()
