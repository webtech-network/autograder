"""HTTP client for the private sandbox control API (see ``sandbox_manager.api``).

Recovery rules:

* acquisition sends a random request id and retries transport failures with
  the same id, so a lost response yields the same handle, never a second
  container;
* disposal (``DELETE``) is idempotent and retried on transport failures; the
  handle's HTTP session is closed in ``finally`` whatever happens;
* commands are never replayed automatically: a lost run response surfaces as
  :class:`RemoteSandboxError`;
* an unknown handle (:class:`SandboxHandleNotFound`), a closed or expired one
  (:class:`SandboxHandleGone`) and a missing artifact (:class:`ArtifactNotFound`,
  a ``FileNotFoundError``) are distinct exceptions;
* a language this host has no runtime for raises
  :class:`~sandbox_manager.errors.RuntimeUnavailableError`, as the local manager does.
"""
import base64
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Dict, List, Optional

import requests

from sandbox_manager.errors import RuntimeUnavailableError
from sandbox_manager.models.api_models import TRANSPORT_MARGIN_SECONDS
from sandbox_manager.models.sandbox_models import CommandResponse, DisposalStatus, ExtractedFile, ResponseCategory
from autograder.models.language import Language

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile

CONNECT_TIMEOUT_SECONDS = 5
ACQUIRE_TIMEOUT_SECONDS = 90     # May create a container (image start, gVisor).
TRANSFER_TIMEOUT_SECONDS = 120   # Up to 5 MiB of files or 32 MiB of fixtures.
DISPOSE_TIMEOUT_SECONDS = 60
STATS_TIMEOUT_SECONDS = 10
TRANSPORT_ERRORS = (requests.ConnectionError, requests.Timeout)


class RemoteSandboxError(RuntimeError):
    """The control API or its transport failed."""
    def __init__(self, message: str, *, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class SandboxHandleNotFound(RemoteSandboxError):
    """The service does not know this handle (never issued, or forgotten after a restart)."""


class SandboxHandleGone(RemoteSandboxError):
    """The handle was closed or expired and its sandbox disposed."""


class SandboxUnavailable(RemoteSandboxError):
    """No sandbox can be handed out now (capacity or handle limit)."""


class ArtifactNotFound(FileNotFoundError):
    """The handle is valid but the requested artifact does not exist."""


def _error_detail(response: requests.Response):
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict):
        return detail.get("code"), detail.get("message") or response.reason
    return None, response.reason


def _checked(response: requests.Response, *, artifact_path: Optional[str] = None) -> dict:
    if response.status_code < 400:
        return response.json() if response.content else {}
    code, message = _error_detail(response)
    text = f"Sandbox control API error {response.status_code} ({code or 'UNKNOWN'}): {message}"
    if code == "ARTIFACT_NOT_FOUND" and artifact_path is not None:
        raise ArtifactNotFound(f"File not found in container: {artifact_path}")
    if code == "ARTIFACT_INVALID":
        raise ValueError(message)
    if code == "HANDLE_NOT_FOUND":
        raise SandboxHandleNotFound(text, status_code=response.status_code, code=code)
    if response.status_code == 410:
        raise SandboxHandleGone(text, status_code=response.status_code, code=code)
    if code == "RUNTIME_UNAVAILABLE":
        raise RuntimeUnavailableError(f"The sandbox service has no runtime for this language: {message}")
    if code in ("SANDBOX_UNAVAILABLE", "HANDLE_LIMIT"):
        raise SandboxUnavailable(text, status_code=response.status_code, code=code)
    raise RemoteSandboxError(text, status_code=response.status_code, code=code)


def _new_session(token: Optional[str]) -> requests.Session:
    session = requests.Session()
    # requests' default adapter performs no retries; replay policy lives here.
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def _command(data: dict) -> CommandResponse:
    return CommandResponse(stdout=data["stdout"], stderr=data["stderr"], exit_code=data["exit_code"],
                           execution_time=data["execution_time"], category=ResponseCategory(data["category"]))


class RemoteSandboxContainer:
    """One remote handle; matches the operations of ``SandboxContainer`` used by hosts."""

    def __init__(self, sandbox_id: str, language: Language, api_url: str, token: Optional[str] = None):
        self.sandbox_id = sandbox_id
        self.language = language
        self.api_url = api_url.rstrip('/')
        self.disposal_status: Optional[DisposalStatus] = None
        self._session = _new_session(token)

    @property
    def _base(self) -> str:
        return f"{self.api_url}/sandboxes/{self.sandbox_id}"

    def _send(self, method: str, path: str, *, read_timeout: float, **kwargs) -> requests.Response:
        try:
            return self._session.request(method, self._base + path,
                                         timeout=(CONNECT_TIMEOUT_SECONDS, read_timeout), **kwargs)
        except TRANSPORT_ERRORS as exc:
            raise RemoteSandboxError(f"Sandbox control API unreachable during {path or 'request'}: "
                                     f"{type(exc).__name__}", code="TRANSPORT_ERROR") from exc

    def close(self):
        """Close this handle's HTTP session (idempotent)."""
        self._session.close()

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        """Stage submission files under /app."""
        files = {name: {"filename": sf.filename, "content": sf.content} for name, sf in submission_files.items()}
        _checked(self._send("POST", "/prepare", json={"submission_files": files},
                            read_timeout=TRANSFER_TIMEOUT_SECONDS))

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """Stage fixtures under /tmp."""
        assets = [{"target": asset.target, "content": base64.b64encode(asset.content).decode('ascii'),
                   "read_only": asset.read_only} for asset in resolved_assets]
        _checked(self._send("POST", "/inject", json={"resolved_assets": assets},
                            read_timeout=TRANSFER_TIMEOUT_SECONDS))

    def run_command(self, command: str, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """Run once. Never replayed: a lost response raises RemoteSandboxError."""
        response = self._send("POST", "/run", json={"command": command, "timeout": timeout, "workdir": workdir},
                              read_timeout=timeout + TRANSPORT_MARGIN_SECONDS)
        return _command(_checked(response))

    def run_commands(self, commands: List[str], program_command: str = None, timeout: int = 30,
                     workdir: str = "/app") -> CommandResponse:
        """Run once. Never replayed: a lost response raises RemoteSandboxError."""
        payload = {"commands": commands, "program_command": program_command, "timeout": timeout,
                   "workdir": workdir}
        response = self._send("POST", "/run-batch", json=payload, read_timeout=timeout + TRANSPORT_MARGIN_SECONDS)
        return _command(_checked(response))

    def extract_file(self, path: str, max_bytes: int = 1_048_576) -> ExtractedFile:
        """Read one artifact; a missing file raises ArtifactNotFound."""
        response = self._send("GET", "/files", params={"path": path, "max_bytes": max_bytes},
                              read_timeout=TRANSFER_TIMEOUT_SECONDS)
        data = _checked(response, artifact_path=path)
        return ExtractedFile(path=data["path"], content_bytes=base64.b64decode(data["content_bytes"]),
                             size=data["size"], content_text=data["content_text"], encoding=data["encoding"])


class RemoteSandboxManager:
    """Client for the control API; same acquire/dispose surface as ``SandboxManager``."""

    def __init__(self, api_url: str, token: Optional[str] = None, *, acquire_attempts: int = 3,
                 dispose_attempts: int = 3):
        self.api_url = api_url.rstrip('/')
        self.token = token
        self.acquire_attempts = acquire_attempts
        self.dispose_attempts = dispose_attempts
        self._session = _new_session(token)

    def _with_transport_retry(self, attempts: int, send):
        for attempt in range(1, attempts + 1):
            try:
                return send()
            except TRANSPORT_ERRORS as exc:
                if attempt == attempts:
                    raise RemoteSandboxError(f"Sandbox control API unreachable: {type(exc).__name__}",
                                             code="TRANSPORT_ERROR") from exc
        raise AssertionError("unreachable")

    def get_sandbox(self, lang: Language) -> RemoteSandboxContainer:
        """Acquire a handle. Transport retries reuse one request id (no duplicate containers)."""
        request_id = uuid.uuid4().hex
        url = f"{self.api_url}/sandboxes/{lang.value}"
        response = self._with_transport_retry(self.acquire_attempts, lambda: self._session.post(
            url, json={"request_id": request_id}, timeout=(CONNECT_TIMEOUT_SECONDS, ACQUIRE_TIMEOUT_SECONDS)))
        data = _checked(response)
        return RemoteSandboxContainer(sandbox_id=data["sandbox_id"], language=lang, api_url=self.api_url,
                                      token=self.token)

    def dispose(self, sandbox: RemoteSandboxContainer) -> DisposalStatus:
        """Dispose a handle (idempotent). The handle's session is closed in every case."""
        if sandbox.disposal_status is not None:
            return DisposalStatus.ALREADY_DISPOSED
        url = f"{self.api_url}/sandboxes/{sandbox.sandbox_id}"
        try:
            response = self._with_transport_retry(self.dispose_attempts, lambda: self._session.delete(
                url, timeout=(CONNECT_TIMEOUT_SECONDS, DISPOSE_TIMEOUT_SECONDS)))
            status = DisposalStatus(_checked(response)["status"])
            sandbox.disposal_status = status
            return status
        finally:
            sandbox.close()

    @contextmanager
    def acquire_sandbox(self, lang: Language):
        """Acquire a handle and dispose it when the block exits."""
        sandbox = self.get_sandbox(lang)
        try:
            yield sandbox
        finally:
            self.dispose(sandbox)

    def shutdown(self):
        """Close the manager's HTTP session."""
        self._session.close()

    def get_pool_stats(self) -> dict:
        """Pool and handle statistics from the control API."""
        response = self._session.get(f"{self.api_url}/stats",
                                     timeout=(CONNECT_TIMEOUT_SECONDS, STATS_TIMEOUT_SECONDS))
        return _checked(response)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
