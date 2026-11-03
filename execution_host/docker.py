"""Docker host profile. Networking is deliberately absent from pooled sandboxes."""
import os
from threading import Lock

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import relative_path
from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.models.sandbox_models import DisposalStatus


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
        """Dispose the sandbox once; unconfirmed removal is reported as a cleanup error."""
        if self._closed:
            return
        self._closed = True
        status = self.manager.dispose(self.sandbox)
        if status is DisposalStatus.QUARANTINED:
            raise RuntimeError("Sandbox removal was not confirmed; it is quarantined for retry.")


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
    def __init__(self, *, mode="remote", api_url="http://localhost:8001", config_file="sandbox_config.yml",
                 api_token=None):
        self.mode = mode
        self.api_url = api_url
        self.api_token = api_token
        self.config_file = config_file
        self._manager = None
        self._lock = Lock()
        self.capabilities = HostCapabilities(execution=self.acquire,
            fixtures=ConfiguredFixtureProvider(), ai=ConfiguredAssessmentProvider())

    def acquire(self, language):
        with self._lock:
            if self._manager is None:
                if self.mode == "remote":
                    from sandbox_manager.remote_client import RemoteSandboxManager
                    self._manager = RemoteSandboxManager(api_url=self.api_url, token=self.api_token)
                elif self.mode == "local":
                    from sandbox_manager.manager import SandboxManager
                    from sandbox_manager.models.pool_config import SandboxPoolConfig
                    # Reclaims containers of provably dead owners, then starts the pools.
                    self._manager = SandboxManager(SandboxPoolConfig.load_from_yaml(self.config_file))
                else:
                    raise ValueError("Unsupported sandbox host mode")
            manager = self._manager
        return DockerSession(manager, language)

    def close(self):
        """Shut down the manager this host created. Safe to call repeatedly."""
        with self._lock:
            manager, self._manager = self._manager, None
        if manager is not None:
            manager.shutdown()

    @classmethod
    def from_environment(cls):
        return cls(mode=os.environ.get("SANDBOX_MODE", "remote"),
                   api_url=os.environ.get("SANDBOX_API_URL", "http://localhost:8001"),
                   api_token=os.environ.get("SANDBOX_API_TOKEN") or None,
                   config_file=os.environ.get("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
