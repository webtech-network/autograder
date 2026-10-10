"""Docker host profile. Networking is deliberately absent from pooled sandboxes."""
import os
from threading import Lock

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import relative_path
from autograder.models.dataclass.asset import ResolvedAsset


class DockerSession:
    fixture_root = "/tmp/app"

    def __init__(self, manager, language):
        self.manager = manager
        self.language = language
        self.sandbox = manager.get_sandbox(language)
        self._closed = False

    def prepare_workdir(self, files):
        self.sandbox.prepare_workdir(files)

    def stage_fixture(self, path, content, read_only):
        self.sandbox.inject_assets([ResolvedAsset(
            target=f"{self.fixture_root}/{relative_path(path)}", content=content, read_only=read_only)])

    def inject_assets(self, assets):
        """Legacy deliberate-run host paths; grading uses stage_fixture instead."""
        self.sandbox.inject_assets(assets)

    def run_command(self, command, **kwargs):
        return self.sandbox.run_command(command, **kwargs)

    def run_commands(self, inputs, *, program_command, **kwargs):
        return self.sandbox.run_commands(inputs, program_command=program_command, **kwargs)

    def read_artifact(self, path):
        return self.sandbox.extract_file(f"/app/{relative_path(path)}")

    def close(self):
        if not self._closed:
            self._closed = True
            self.manager.destroy_sandbox(self.language, self.sandbox)


class ConfiguredFixtureProvider:
    """Capture configuration now; initialize SDKs only for selected fixture work."""
    def __init__(self):
        names = ("EXTERNAL_ASSETS_IN_MEMORY_CACHE_LIMIT", "EXTERNAL_ASSETS_BUCKET_NAME",
                 "AWS_ACCESS_KEY_ID", "AWS_ACCESS_ID", "AWS_SECRET_ACCESS_KEY",
                 "AWS_REGION", "S3_ENDPOINT_URL")
        self.config = {name: os.environ[name] for name in names if name in os.environ}

    def __call__(self, reference):
        from execution_host.assets.resolver import AssetSourceResolver
        provider = AssetSourceResolver(config=self.config).provider
        content = provider.get_asset(reference, reference)
        if content is None:
            raise RuntimeError("Fixture resolution failed")
        return content


class ConfiguredAssessmentProvider:
    """Capture provider choices once, deferring network and credential lookup."""
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("AUTOGRADER_AI_MODEL", "o4-mini-2025-04-16")
        self.secret_name = os.environ.get("AUTOGRADER_AI_SECRET_NAME", "AUTOGRADER_OPENAI_KEY") if os.environ.get("ENVIRONMENT") == "production" else None
        self.region = os.environ.get("AWS_REGION", "us-east-1")

    def run(self, tests, submission_files, locale="en"):
        from execution_host.openai_provider import AiExecutor
        return AiExecutor(api_key=self.api_key, model=self.model, secret_name=self.secret_name,
                          region=self.region).run(tests, submission_files, locale)


def docker_capabilities(manager):
    """Borrow a host-owned manager; each acquisition returns an owned session."""
    return HostCapabilities(execution=lambda language: DockerSession(manager, language),
                            fixtures=ConfiguredFixtureProvider(), ai=ConfiguredAssessmentProvider())


class DockerHost:
    """Lazy, isolated manager for one host lifetime. Static work starts nothing."""
    def __init__(self, *, mode="remote", api_url="http://localhost:8001", config_file="sandbox_config.yml"):
        self.mode = mode
        self.api_url = api_url
        self.config_file = config_file
        self._manager = None
        self._client = None
        self._lock = Lock()
        self.capabilities = HostCapabilities(execution=self.acquire,
            fixtures=ConfiguredFixtureProvider(), ai=ConfiguredAssessmentProvider())

    def acquire(self, language):
        with self._lock:
            if self._manager is None:
                if self.mode == "remote":
                    from sandbox_manager.remote_client import RemoteSandboxManager
                    self._manager = RemoteSandboxManager(api_url=self.api_url)
                elif self.mode == "local":
                    import docker
                    from sandbox_manager.manager import SandboxManager
                    from sandbox_manager.language_pool import LanguagePool
                    from sandbox_manager.models.pool_config import SandboxPoolConfig
                    self._client = docker.from_env()
                    configs = SandboxPoolConfig.load_from_yaml(self.config_file)
                    self._manager = SandboxManager({config.language: LanguagePool(
                        config.language, config, self._client) for config in configs})
                else:
                    raise ValueError("Unsupported sandbox host mode")
            manager = self._manager
        return DockerSession(manager, language)

    def close(self):
        with self._lock:
            manager, client = self._manager, self._client
            self._manager = self._client = None
        try:
            if manager is not None:
                manager.shutdown()
        finally:
            if client is not None:
                client.close()

    @classmethod
    def from_environment(cls):
        return cls(mode=os.environ.get("SANDBOX_MODE", "remote"),
                   api_url=os.environ.get("SANDBOX_API_URL", "http://localhost:8001"),
                   config_file=os.environ.get("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
