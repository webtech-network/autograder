"""Remote client against a real uvicorn control API (in-memory manager, real HTTP)."""
from unittest.mock import patch

import pytest
import requests
from requests.adapters import HTTPAdapter

from autograder.models.dataclass.submission import SubmissionFile
from execution_host.docker import DockerSession
from sandbox_manager.api import create_app
from sandbox_manager.errors import (
    Disposal, SandboxCleanupError, SandboxHandleError, SandboxTransportError,
)
from sandbox_manager.models.sandbox_models import Language, SandboxState
from sandbox_manager.remote_client import RemoteSandboxManager
from tests.unit.sandbox.fakes import FakeManager, serve

TOKEN = "remote-token-" + "y" * 20


@pytest.fixture
def service():
    manager = FakeManager()
    with serve(create_app(token=TOKEN, manager_factory=lambda: manager)) as url:
        yield url, manager


class LossyAdapter(HTTPAdapter):
    """Deliver a request to the server, then lose its response (once per match)."""

    def __init__(self, method, path_suffix, losses=1):
        super().__init__(max_retries=0)
        self.method, self.path_suffix, self.losses, self.sent = method, path_suffix, losses, 0

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        if request.method == self.method and request.path_url.split("?")[0].endswith(self.path_suffix):
            self.sent += 1
            if self.losses:
                self.losses -= 1
                raise requests.ConnectionError("response lost after the server processed the request")
        return response


class TrackingSession(requests.Session):
    instances = []

    def __init__(self):
        super().__init__()
        self.closed = False
        TrackingSession.instances.append(self)

    def close(self):
        self.closed = True
        super().close()


def lossy_factory(adapter):
    def factory():
        session = TrackingSession()
        session.get_adapter = lambda url: adapter  # survive the client's own mounts
        return session
    return factory


def test_full_lease_over_http_and_session_closure(service):
    url, manager = service
    TrackingSession.instances.clear()
    client = RemoteSandboxManager(url, TOKEN, session_factory=TrackingSession)
    with DockerSession(client, Language.PYTHON) as session:
        session.prepare_workdir({"out.txt": SubmissionFile("out.txt", "hello")})
        assert session.run_command("python3 main.py", timeout=5).stdout == "ran python3 main.py"
        assert session.run_commands(["a", "b"], program_command="cat", timeout=5).stdout == "a\nb"
        assert session.read_artifact("out.txt").content_text == "hello"
        with pytest.raises(FileNotFoundError):
            session.read_artifact("missing.txt")
        lease_session = TrackingSession.instances[-1]
    assert manager.leased[0].state is SandboxState.STOPPED
    assert lease_session.closed
    assert client.dispose(session.sandbox) is Disposal.ALREADY_DISPOSED
    with pytest.raises(SandboxHandleError) as closed:
        session.run_command("id")
    assert closed.value.code == "sandbox_expired"


def test_client_preserves_unknown_expired_and_execution_failure(service):
    url, manager = service
    client = RemoteSandboxManager(url, TOKEN)
    sandbox = client.acquire(Language.PYTHON)
    with pytest.raises(SandboxTransportError) as failed:
        sandbox.run_command("explode")
    assert failed.value.code == "execution_failed" and not isinstance(failed.value, FileNotFoundError)

    forged = client.acquire(Language.PYTHON)
    forged.sandbox_id = "f" * 32  # a handle this client does not own
    with pytest.raises(SandboxHandleError) as unknown:
        forged.extract_file("/app/output.txt")
    assert unknown.value.code == "sandbox_not_found"
    assert not isinstance(unknown.value, FileNotFoundError)

    manager.leased[0].state = SandboxState.STOPPED  # the service expired the lease
    with pytest.raises(SandboxHandleError) as expired:
        sandbox.extract_file("/app/output.txt")
    assert expired.value.code == "sandbox_expired"
    assert client.dispose(sandbox) is Disposal.DISPOSED  # expiry already confirmed destruction


def test_wrong_token_is_rejected(service):
    url, _ = service
    with pytest.raises(SandboxTransportError) as rejected:
        RemoteSandboxManager(url, "not-the-token").acquire(Language.PYTHON)
    assert rejected.value.code == "unauthorized"
    with pytest.raises(ValueError):
        RemoteSandboxManager(url, "")


def test_lost_acquire_response_is_replayed_to_the_same_handle(service):
    url, manager = service
    adapter = LossyAdapter("POST", "/sandboxes/python")
    client = RemoteSandboxManager(url, TOKEN, session_factory=lossy_factory(adapter), retry_delay=0)
    sandbox = client.acquire(Language.PYTHON)
    assert adapter.sent == 2 and len(manager.leased) == 1
    assert client.dispose(sandbox) is Disposal.DISPOSED


def test_lost_delete_response_then_retry_confirms_closure(service):
    url, manager = service
    adapter = LossyAdapter("DELETE", "", losses=1)
    TrackingSession.instances.clear()
    client = RemoteSandboxManager(url, TOKEN, session_factory=lossy_factory(adapter), retry_delay=0)
    sandbox = client.acquire(Language.PYTHON)
    assert client.dispose(sandbox) is Disposal.DISPOSED
    assert adapter.sent == 2 and manager.dispose_calls == 1
    assert all(session.closed for session in TrackingSession.instances)


def test_commands_are_never_replayed_after_a_lost_response(service):
    url, manager = service
    adapter = LossyAdapter("POST", "/run")
    client = RemoteSandboxManager(url, TOKEN, session_factory=lossy_factory(adapter), retry_delay=0)
    sandbox = client.acquire(Language.PYTHON)
    with pytest.raises(SandboxTransportError, match="outcome is unknown"):
        sandbox.run_command("python3 main.py", timeout=5)
    assert adapter.sent == 1 and manager.leased[0].runs == ["python3 main.py"]
    client.dispose(sandbox)


def test_session_closes_when_disposal_fails(service):
    url, manager = service
    TrackingSession.instances.clear()
    client = RemoteSandboxManager(url, TOKEN, session_factory=TrackingSession, retry_delay=0)
    sandbox = client.acquire(Language.PYTHON)
    manager.dispose_failures = 1
    with pytest.raises(SandboxCleanupError):
        client.dispose(sandbox)  # 202: the service retains the record
    assert TrackingSession.instances[-1].closed
    assert not sandbox.disposed
    # The host retries (a later close, or host shutdown) with a fresh session.
    assert client.dispose(sandbox) is Disposal.DISPOSED
    assert all(session.closed for session in TrackingSession.instances)


def test_unreachable_service_still_closes_the_session():
    TrackingSession.instances.clear()
    client = RemoteSandboxManager("http://127.0.0.1:9", TOKEN, session_factory=TrackingSession, retry_delay=0)
    with pytest.raises(SandboxTransportError):
        client.acquire(Language.PYTHON)
    assert TrackingSession.instances and all(session.closed for session in TrackingSession.instances)


def test_disposal_transport_failure_closes_session_and_reports(service):
    url, manager = service
    TrackingSession.instances.clear()
    client = RemoteSandboxManager(url, TOKEN, session_factory=TrackingSession, retry_delay=0)
    sandbox = client.acquire(Language.PYTHON)
    with patch.object(requests.Session, "delete", side_effect=requests.ConnectionError("down")):
        with pytest.raises(SandboxTransportError):
            client.dispose(sandbox)
    assert all(session.closed for session in TrackingSession.instances)
    client.shutdown()  # host shutdown retries the unconfirmed lease and confirms it
    assert manager.leased[0].state is SandboxState.STOPPED
