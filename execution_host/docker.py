"""Docker host profile. Networking is deliberately absent from pooled sandboxes."""
import logging
import os
from threading import Lock

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import relative_path
from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.evaluation_error import EvaluationError
from execution_host.fixtures import S3FixtureProvider
from sandbox_manager.errors import SandboxLifetimeExceeded
from sandbox_manager.models.sandbox_models import DisposalStatus

logger = logging.getLogger(__name__)
DEFAULT_AI_MODEL = "o4-mini-2025-04-16"

#: How long a grading waits for a slot of the host sandbox budget before it fails
#: as a retryable capability error. Waiting happens while the HTTP lease is renewed
#: and before any sandbox clock starts; deliberate execution passes a short wait.
GRADING_CAPACITY_WAIT_SECONDS = 600.0


class DockerSession:
    """One sandbox that stops by itself ``budget.session_seconds`` after its grant.

    Without a budget it lives the host's ``running_timeout``. A budget the host
    does not grant is refused before waiting: ``EXECUTION_BUDGET_EXCEEDED``.
    """
    fixture_root = "/tmp/app"

    def __init__(self, manager, language, budget=None, wait_seconds=GRADING_CAPACITY_WAIT_SECONDS):
        self.manager = manager
        self.language = language
        try:
            self.sandbox = manager.get_sandbox(language, wait_seconds=wait_seconds,
                                               lifetime_seconds=budget.session_seconds if budget else None)
        except SandboxLifetimeExceeded as exc:
            raise EvaluationError("EXECUTION_BUDGET_EXCEEDED",
                                  "The definition needs more execution time than this host grants.",
                                  "capability") from exc
        self._closed = False

    def prepare_workdir(self, files):
        self.sandbox.prepare_workdir(files)

    def stage_fixtures(self, fixtures):
        """The whole set as one ``inject_assets`` call: one transfer (one request in remote mode)."""
        self.sandbox.inject_assets([ResolvedAsset(
            target=f"{self.fixture_root}/{relative_path(fixture.path)}", content=fixture.content,
            read_only=fixture.read_only) for fixture in fixtures])

    def inject_assets(self, assets):
        """Legacy deliberate-run host paths; grading uses stage_fixtures instead."""
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
    ``deadline_seconds`` bounds one ``assess`` call (connect plus the request).
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

    @property
    def deadline_seconds(self) -> float:
        """The longest one ``assess`` call can take: connecting plus the one request, never retried."""
        from execution_host import openai_provider
        return openai_provider.CONNECT_TIMEOUT_SECONDS + openai_provider.REQUEST_TIMEOUT_SECONDS

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
    """Borrow a host-owned local manager; each acquisition returns an owned session."""
    return HostCapabilities(execution=lambda language, budget: DockerSession(manager, language, budget),
                            fixtures=S3FixtureProvider.from_environment(),
                            ai=ConfiguredAssessmentProvider.from_environment(),
                            max_session_seconds=manager.running_timeout)


class DockerHost:
    """Isolated manager for one host lifetime. Static work starts nothing.

    The mode, the provider settings and the sandbox configuration's host
    maximum are validated at construction; Docker and the network are first
    used by :meth:`start` or, for a host that never calls it (the Action), by
    the first acquisition.
    """
    def __init__(self, *, mode="remote", api_url="http://localhost:8001", config_file="sandbox_config.yml",
                 api_token=None):
        from sandbox_manager.models.pool_config import SandboxHostConfig
        if mode not in ("local", "remote"):
            raise ValueError(f"SANDBOX_MODE must be local or remote, got {mode!r}")
        self.mode = mode
        self.api_url = api_url
        self.api_token = api_token
        self.config_file = config_file
        # The host maximum: the longest sandbox lifetime this host grants. A remote
        # host reads the same sandbox_config.yml as its control service, which
        # enforces it again (LIFETIME_EXCEEDED) at acquisition. Without the file
        # (a library install) nothing is checked early; acquisition still refuses.
        try:
            self.max_session_seconds = SandboxHostConfig.load_from_yaml(config_file).running_timeout
        except FileNotFoundError:
            logger.warning("Sandbox configuration %s not found: execution budgets are checked only at "
                           "sandbox acquisition", config_file)
            self.max_session_seconds = None
        self._manager = None
        self._lock = Lock()
        self.capabilities = HostCapabilities(execution=self.acquire,
            fixtures=S3FixtureProvider.from_environment(),
            ai=ConfiguredAssessmentProvider.from_environment(),
            max_session_seconds=self.max_session_seconds)

    def start(self):
        """Start a local manager now, so a host that cannot execute fails at service start.

        The manager validates the sandbox configuration, the configured runtime
        (``IsolationRuntimeError`` when Docker does not offer it) and the runtime
        images. A long-running service calls this before it reports ready; in
        remote mode the control service performs the same checks in its own startup.
        """
        if self.mode == "local":
            self._get_manager()

    def acquire(self, language, budget=None, wait_seconds=GRADING_CAPACITY_WAIT_SECONDS):
        """An owned session for ``budget``; waits up to ``wait_seconds`` for a slot of the sandbox budget."""
        return DockerSession(self._get_manager(), language, budget, wait_seconds)

    def _get_manager(self):
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
            return self._manager

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
