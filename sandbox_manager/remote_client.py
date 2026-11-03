"""HTTP client for the private sandbox control API.

It has the same lease API as the local :class:`~sandbox_manager.manager.SandboxManager`:
``acquire(language)`` returns a sandbox the caller owns, ``dispose(sandbox)``
ends the lease idempotently. Each lease owns one HTTP session, which is closed
by ``dispose`` on every path, including failure.

Replay policy: acquisition is retried once with the same lease secret (the
server returns the same handle), and disposal is retried because it is
idempotent. Workdir preparation, fixture staging, commands and HTTP requests
are never replayed automatically: their outcome is uncertain after a lost
response.
"""
import base64
import logging
import secrets
import threading
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter

from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, Disposal, RuntimeUnavailableError,
    SandboxCleanupError, SandboxHandleError, SandboxInvalidatedError, SandboxTransportError,
)
from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessResult
from sandbox_manager.models.api_models import ProcessRequestModel, ProcessResultModel
from sandbox_manager.models.sandbox_models import ExtractedFile, HttpResponse

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile

logger = logging.getLogger(__name__)

LEASE_HEADER = "X-Sandbox-Lease"
TRANSPORT_MARGIN_SECONDS = 15   # server-side work beyond the process timeout
ACQUIRE_TIMEOUT_SECONDS = 120   # scale-up may create a container
STAGING_TIMEOUT_SECONDS = 120
DISPOSE_TIMEOUT_SECONDS = 60
DISPOSE_ATTEMPTS = 3
# Every requests failure (connection, timeout, broken chunked body, ...) leaves the
# outcome unknown; none may escape as a non-RuntimeError (ConnectionError is OSError).
_TRANSIENT = (requests.RequestException,)


def _error_code(response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return ""
    return detail.get("code", "") if isinstance(detail, dict) else ""


def _raise_for(response, operation: str) -> None:
    """Translate a control API error into a distinct client exception."""
    if response.status_code < 400:
        return
    code = _error_code(response)
    if code in ("sandbox_not_found", "sandbox_expired"):
        raise SandboxHandleError(code, f"Sandbox lease unavailable during {operation} ({code})")
    if code == "runtime_unavailable":
        raise RuntimeUnavailableError(f"The sandbox service has no runtime for this language ({operation})")
    if code == "sandbox_invalidated":
        raise SandboxInvalidatedError(f"The sandbox was invalidated ({operation})")
    if code == "artifact_read_failed":
        raise ArtifactReadError(f"The artifact could not be read back ({operation})")
    if code == "artifact_not_found":
        raise FileNotFoundError(f"Artifact not found in sandbox during {operation}")
    if code == "artifact_too_large":
        raise ArtifactTooLargeError(f"Artifact exceeds the requested size limit during {operation}")
    raise SandboxTransportError(
        f"Sandbox control API {operation} failed with HTTP {response.status_code} ({code or 'no code'})",
        code=code or f"http_{response.status_code}")


class RemoteSandboxContainer:
    """A leased remote sandbox. Matches the operations of ``SandboxContainer``."""

    def __init__(self, *, sandbox_id: str, language: Language, api_url: str, secret: str,
                 session: requests.Session, lease_seconds: int):
        self.sandbox_id = sandbox_id
        self.language = language
        self.api_url = api_url
        self.lease_seconds = lease_seconds
        self._secret = secret
        self._session: Optional[requests.Session] = session
        self.disposed = False

    @property
    def secret(self) -> str:
        return self._secret

    def _url(self, suffix: str = "") -> str:
        return f"{self.api_url}/sandboxes/{self.sandbox_id}{suffix}"

    def _call(self, method: str, suffix: str, operation: str, *, timeout: float, **kwargs):
        session = self._session
        if session is None:
            raise SandboxHandleError("sandbox_expired", f"The sandbox lease is closed; {operation} is unavailable")
        try:
            response = session.request(method, self._url(suffix), timeout=timeout, **kwargs)
        except _TRANSIENT as exc:
            # Never replayed: the server may already have executed this operation.
            raise SandboxTransportError(f"Sandbox control API {operation} outcome is unknown: {exc}") from exc
        _raise_for(response, operation)
        return response

    def take_session(self) -> Optional[requests.Session]:
        session, self._session = self._session, None
        return session

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        files = {name: {"filename": item.filename, "content": item.content}
                 for name, item in submission_files.items()}
        self._call("POST", "/prepare", "workdir preparation", timeout=STAGING_TIMEOUT_SECONDS,
                   json={"submission_files": files})

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        assets = [{"target": item.target, "content": base64.b64encode(item.content).decode("ascii"),
                   "read_only": item.read_only} for item in resolved_assets]
        self._call("POST", "/inject", "fixture staging", timeout=STAGING_TIMEOUT_SECONDS,
                   json={"resolved_assets": assets})

    def run_process(self, request: ProcessRequest) -> ProcessResult:
        """Run one process remotely. A lost response is an unknown outcome: never replayed."""
        body = ProcessRequestModel.from_request(request).model_dump(mode="json")
        response = self._call("POST", "/process", "process execution",
                              timeout=request.timeout + TRANSPORT_MARGIN_SECONDS, json=body)
        return ProcessResultModel.model_validate(response.json()).to_result()

    def extract_file(self, path: str, max_bytes: int = 1_048_576) -> ExtractedFile:
        data = self._call("GET", "/files", "artifact extraction", timeout=STAGING_TIMEOUT_SECONDS,
                          params={"path": path, "max_bytes": max_bytes}).json()
        return ExtractedFile(path=data["path"], content_bytes=base64.b64decode(data["content_bytes"]),
                             size=data["size"], content_text=data["content_text"], encoding=data["encoding"])

    def make_request(self, method: str, endpoint: str, **kwargs) -> HttpResponse:
        timeout = kwargs.get("timeout") or 30
        data = self._call("POST", "/request", "HTTP request", timeout=timeout + TRANSPORT_MARGIN_SECONDS,
                          json={"method": method, "endpoint": endpoint, "kwargs": kwargs}).json()
        response = requests.Response()
        response.status_code = data["status_code"]
        response._content = base64.b64decode(data["content"])  # pylint: disable=protected-access
        response.headers = data["headers"]
        response.url = f"http://remote-sandbox{endpoint}"
        return HttpResponse(response)


class RemoteSandboxManager:
    """Client-side lease owner for one host. Borrowed by sessions, owned by the host."""

    def __init__(self, api_url: str, token: str, *, session_factory: Callable[[], requests.Session] = requests.Session,
                 retry_delay: float = 0.5):
        if not token:
            raise ValueError("A sandbox control API token (SANDBOX_API_TOKEN) is required for remote mode")
        self.api_url = api_url.rstrip("/")
        self._token = token
        self._session_factory = session_factory
        self._retry_delay = retry_delay
        self._leases: set = set()
        self._lock = threading.Lock()
        self._closed = False

    def _new_session(self, secret: str) -> requests.Session:
        session = self._session_factory()
        adapter = HTTPAdapter(max_retries=0)  # replay is decided explicitly, per operation
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"Authorization": f"Bearer {self._token}", LEASE_HEADER: secret})
        return session

    def start(self) -> "RemoteSandboxManager":
        return self

    def acquire(self, language: Language) -> RemoteSandboxContainer:
        if self._closed:
            raise SandboxTransportError("The remote sandbox client is shut down", code="client_closed")
        secret = secrets.token_urlsafe(32)
        session = self._new_session(secret)
        try:
            response = None
            for attempt in (1, 2):
                try:
                    response = session.post(f"{self.api_url}/sandboxes/{language.value}",
                                            timeout=ACQUIRE_TIMEOUT_SECONDS)
                    break
                except _TRANSIENT as exc:
                    if attempt == 2:
                        raise SandboxTransportError(f"Sandbox acquisition failed: {exc}") from exc
                    time.sleep(self._retry_delay)  # same secret: the server replays the same handle
            _raise_for(response, "acquisition")
            data = response.json()
        except BaseException:
            session.close()
            raise
        sandbox = RemoteSandboxContainer(sandbox_id=data["sandbox_id"], language=language, api_url=self.api_url,
                                         secret=secret, session=session, lease_seconds=data["lease_seconds"])
        with self._lock:
            self._leases.add(sandbox)
        return sandbox

    def dispose(self, sandbox: RemoteSandboxContainer) -> Disposal:
        """End a lease. Retries transport loss; always closes the lease's HTTP session."""
        if sandbox.disposed:
            return Disposal.ALREADY_DISPOSED
        session = sandbox.take_session() or self._new_session(sandbox.secret)
        try:
            failure = None
            for attempt in range(1, DISPOSE_ATTEMPTS + 1):
                try:
                    response = session.delete(f"{self.api_url}/sandboxes/{sandbox.sandbox_id}",
                                              timeout=DISPOSE_TIMEOUT_SECONDS)
                except _TRANSIENT as exc:
                    failure = SandboxTransportError(f"Sandbox disposal response was lost: {exc}")
                else:
                    if response.status_code == 200:
                        sandbox.disposed = True
                        with self._lock:
                            self._leases.discard(sandbox)
                        return Disposal.DISPOSED
                    if response.status_code == 202:
                        raise SandboxCleanupError("The sandbox service retained this sandbox for cleanup retry")
                    if response.status_code < 500:
                        _raise_for(response, "disposal")
                    failure = SandboxTransportError(f"Sandbox disposal failed with HTTP {response.status_code}")
                if attempt < DISPOSE_ATTEMPTS:
                    time.sleep(self._retry_delay * attempt)
            raise failure
        finally:
            session.close()

    def shutdown(self) -> None:
        """Dispose leases still held by this host. Safe to repeat."""
        self._closed = True
        with self._lock:
            remaining = list(self._leases)
        failures = 0
        for sandbox in remaining:
            try:
                self.dispose(sandbox)
            except Exception:  # pylint: disable=broad-exception-caught
                failures += 1
                logger.exception("Remote sandbox %s cleanup failed at shutdown", sandbox.sandbox_id[:8])
        if failures:
            raise SandboxCleanupError(f"{failures} remote sandbox lease(s) could not be confirmed closed; "
                                      "the service expires them")

    def get_pool_stats(self) -> dict:
        session = self._new_session("")
        try:
            response = session.get(f"{self.api_url}/stats", timeout=10)
            _raise_for(response, "stats")
            return response.json()
        finally:
            session.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
