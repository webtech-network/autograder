"""Docker host profile. Networking is deliberately absent from pooled sandboxes."""
import logging
import os
from threading import Lock

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import relative_path
from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.evaluation_error import EvaluationError
from execution_host.fixtures import S3FixtureProvider
from sandbox_manager.models.sandbox_models import DisposalStatus

logger = logging.getLogger(__name__)
DEFAULT_AI_MODEL = "o4-mini-2025-04-16"

#: How long a grading waits for a slot of the host sandbox budget before it fails
#: as a retryable capability error. Waiting happens while the HTTP lease is renewed
#: and before any sandbox clock starts; deliberate execution passes a short wait.
GRADING_CAPACITY_WAIT_SECONDS = 600.0


class DockerSession:
    fixture_root = "/tmp/app"

    def __init__(self, manager, language, wait_seconds=GRADING_CAPACITY_WAIT_SECONDS):
        self.manager = manager
        self.language = language
        self.sandbox = manager.get_sandbox(language, wait_seconds=wait_seconds)
        self._closed = False

    def prepare_workdir(self, files):
        self.sandbox.prepare_workdir(files)

    def stage_fixture(self, path, content, read_only):
        self.sandbox.inject_assets([ResolvedAsset(
            target=f"{self.fixture_root}/{relative_path(path)}", content=content, read_only=read_only)])

    def inject_assets(self, assets):
        """Legacy deliberate-run host paths; grading uses stage_fixture instead."""
        self.sandbox.inject_assets(assets)

    def run_process(self, request):
        return self.sandbox.run_process(request)

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


class ConfiguredAssessmentProvider:
    """The host's OpenAI provider: one credential lookup and one client per host lifetime.

    Nothing is resolved until the first selected AI criterion, so static and I/O
    gradings never touch credentials or the network. Concurrent first calls share
    one resolution. A failed resolution is ``PROVIDER_UNAVAILABLE`` and is not
    cached. A rejected credential (HTTP 401) drops the client, so the next AI
    grading looks the key up again and a rotated secret needs no restart.
    ``secret_source`` and ``client_factory`` let a host (or a test) supply its own.
    """

    def __init__(self, *, api_key=None, model=DEFAULT_AI_MODEL, secret_name=None, region="us-east-1",
                 secret_source=None, client_factory=None):
        self.api_key = api_key
        self.model = model
        self.secret_name = secret_name
        self.region = region
        self._secret_source = secret_source
        self._client_factory = client_factory
        self._executor = None
        self._lock = Lock()

    @classmethod
    def from_environment(cls, environ=None, **overrides):
        config = os.environ if environ is None else environ
        production = config.get("ENVIRONMENT") == "production"
        return cls(api_key=config.get("OPENAI_API_KEY"), model=config.get("AUTOGRADER_AI_MODEL", DEFAULT_AI_MODEL),
                   secret_name=config.get("AUTOGRADER_AI_SECRET_NAME", "AUTOGRADER_OPENAI_KEY") if production else None,
                   region=config.get("AWS_REGION", "us-east-1"), **overrides)

    def _get_executor(self):
        with self._lock:
            if self._executor is None:
                from execution_host import openai_provider
                try:
                    api_key = openai_provider.resolve_api_key(
                        api_key=self.api_key, secret_name=self.secret_name, region=self.region,
                        secret_source=self._secret_source)
                    client = (self._client_factory or openai_provider.openai_client)(api_key)
                except Exception as exc:
                    logger.exception("Assessment provider initialization failed")
                    raise EvaluationError("PROVIDER_UNAVAILABLE", "The assessment provider is unavailable.",
                                          "provider") from exc
                self._executor = openai_provider.AiExecutor(client, self.model)
            return self._executor

    def assess(self, requests, *, context_files, locale="en"):
        if not requests:
            return []
        executor = self._get_executor()
        try:
            return executor.assess(requests, context_files=context_files, locale=locale)
        except EvaluationError as error:
            from openai import AuthenticationError
            if isinstance(error.__cause__, AuthenticationError):
                with self._lock:
                    if self._executor is executor:
                        self._executor = None
            raise


def docker_capabilities(manager):
    """Borrow a host-owned manager; each acquisition returns an owned session."""
    return HostCapabilities(execution=lambda language: DockerSession(manager, language),
                            fixtures=S3FixtureProvider.from_environment(),
                            ai=ConfiguredAssessmentProvider.from_environment())


class DockerHost:
    """Lazy, isolated manager for one host lifetime. Static work starts nothing.

    The mode and the provider settings are validated at construction; the
    sandbox configuration, Docker and the network are first used by the first
    acquisition.
    """
    def __init__(self, *, mode="remote", api_url="http://localhost:8001", config_file="sandbox_config.yml",
                 api_token=None):
        if mode not in ("local", "remote"):
            raise ValueError(f"SANDBOX_MODE must be local or remote, got {mode!r}")
        self.mode = mode
        self.api_url = api_url
        self.api_token = api_token
        self.config_file = config_file
        self._manager = None
        self._lock = Lock()
        self.capabilities = HostCapabilities(execution=self.acquire,
            fixtures=S3FixtureProvider.from_environment(),
            ai=ConfiguredAssessmentProvider.from_environment())

    def acquire(self, language, wait_seconds=GRADING_CAPACITY_WAIT_SECONDS):
        """An owned session; waits up to ``wait_seconds`` for a slot of the sandbox budget."""
        with self._lock:
            if self._manager is None:
                if self.mode == "remote":
                    from sandbox_manager.remote_client import RemoteSandboxManager
                    self._manager = RemoteSandboxManager(api_url=self.api_url, token=self.api_token)
                else:
                    from sandbox_manager.manager import SandboxManager
                    from sandbox_manager.models.pool_config import SandboxHostConfig
                    # Reclaims containers of provably dead owners, then starts the pools.
                    self._manager = SandboxManager.from_config(SandboxHostConfig.load_from_yaml(self.config_file))
            manager = self._manager
        return DockerSession(manager, language, wait_seconds)

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
