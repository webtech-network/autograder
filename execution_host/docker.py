"""Docker host profile. Networking is deliberately absent from pooled sandboxes."""
import os
from threading import Lock

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import relative_path
from autograder.models.dataclass.asset import ResolvedAsset
from execution_host.fixtures import S3FixtureProvider


class DockerSession:
    """One sandbox lease: acquisition, preparation, use and disposal.

    The session borrows its manager (owned by the host) and owns exactly one
    sandbox. ``close`` disposes it; repeating ``close`` after confirmation is a
    no-op, and repeating it after a ``SandboxCleanupError`` retries disposal.
    """
    fixture_root = "/tmp/app"

    def __init__(self, manager, language):
        self.manager = manager
        self.language = language
        self.sandbox = manager.acquire(language)
        self._closed = False

    def prepare_workdir(self, files):
        self.sandbox.prepare_workdir(files)

    def stage_fixture(self, path, content, read_only):
        self.sandbox.inject_assets([ResolvedAsset(
            target=f"{self.fixture_root}/{relative_path(path)}", content=content, read_only=read_only)])

    def inject_assets(self, assets):
        """Deliberate-run host path; grading uses stage_fixture instead."""
        self.sandbox.inject_assets(assets)

    def run_process(self, request):
        return self.sandbox.run_process(request)

    def read_artifact(self, path):
        return self.sandbox.extract_file(f"/app/{relative_path(path)}")

    def close(self):
        if not self._closed:
            self.manager.dispose(self.sandbox)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class ConfiguredAssessmentProvider:
    """Capture provider choices once, deferring network and credential lookup."""
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("AUTOGRADER_AI_MODEL", "o4-mini-2025-04-16")
        self.secret_name = os.environ.get("AUTOGRADER_AI_SECRET_NAME", "AUTOGRADER_OPENAI_KEY") if os.environ.get("ENVIRONMENT") == "production" else None
        self.region = os.environ.get("AWS_REGION", "us-east-1")

    def assess(self, requests, *, context_files, locale="en"):
        from execution_host.openai_provider import AiExecutor
        return AiExecutor(api_key=self.api_key, model=self.model, secret_name=self.secret_name,
                          region=self.region).assess(requests, context_files=context_files, locale=locale)


def docker_capabilities(manager):
    """Borrow a host-owned manager; each acquisition returns an owned session."""
    return HostCapabilities(execution=lambda language: DockerSession(manager, language),
                            fixtures=S3FixtureProvider.from_environment(), ai=ConfiguredAssessmentProvider())


class DockerHost:
    """Lazy, isolated manager for one host lifetime. Static work starts nothing.

    The host owns the manager: the first acquisition starts it (taking Docker
    ownership and reclaiming provably dead owners in local mode) and ``close``
    shuts it down. Signal handling stays with the host process (uvicorn or the
    Actions entrypoint), never with this library.
    """
    def __init__(self, *, mode="remote", api_url="http://localhost:8001", config_file="sandbox_config.yml",
                 api_token=None, lease_dir=None):
        if mode not in ("local", "remote"):
            raise ValueError("Unsupported sandbox host mode")
        self.mode = mode
        self.api_url = api_url
        self.config_file = config_file
        self.api_token = api_token
        self.lease_dir = lease_dir
        self._manager = None
        self._closed = False
        self._lock = Lock()
        self.capabilities = HostCapabilities(execution=self.acquire,
            fixtures=S3FixtureProvider.from_environment(), ai=ConfiguredAssessmentProvider())

    def _start_manager(self):
        if self.mode == "remote":
            from sandbox_manager.remote_client import RemoteSandboxManager
            return RemoteSandboxManager(api_url=self.api_url, token=self.api_token).start()
        from sandbox_manager.manager import SandboxManager
        from sandbox_manager.models.pool_config import SandboxPoolConfig
        return SandboxManager(SandboxPoolConfig.load_from_yaml(self.config_file), lease_dir=self.lease_dir).start()

    def acquire(self, language):
        with self._lock:
            if self._closed:
                raise RuntimeError("The sandbox host is closed")
            if self._manager is None:
                self._manager = self._start_manager()
            manager = self._manager
        return DockerSession(manager, language)

    def close(self):
        with self._lock:
            manager, self._manager, self._closed = self._manager, None, True
        if manager is not None:
            manager.shutdown()

    @classmethod
    def from_environment(cls):
        return cls(mode=os.environ.get("SANDBOX_MODE", "remote"),
                   api_url=os.environ.get("SANDBOX_API_URL", "http://localhost:8001"),
                   config_file=os.environ.get("SANDBOX_CONFIG_FILE", "sandbox_config.yml"),
                   api_token=os.environ.get("SANDBOX_API_TOKEN") or None,
                   lease_dir=os.environ.get("SANDBOX_LEASE_DIR") or None)
