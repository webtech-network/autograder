"""The private control API over HTTP with a real Docker-backed manager."""
import socket
import threading
import time

import docker
import pytest
import requests
import uvicorn

from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import DisposalStatus
from autograder.models.language import Language
from autograder.models.process import ProcessRequest
from sandbox_manager.ownership import APP_LABEL_VALUE, LABEL_APP, LABEL_OWNER
from sandbox_manager.remote_client import ArtifactNotFound, RemoteSandboxManager, SandboxHandleGone
from tests.sandbox_profiles import TEST_IMAGES

TOKEN = "integration-token"


@pytest.fixture(scope="module")
def service():
    try:
        client = docker.from_env()
        client.images.get(TEST_IMAGES[Language.PYTHON])
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"Docker or {TEST_IMAGES[Language.PYTHON]} unavailable: {exc}")
    holder = {}

    def factory():
        holder["manager"] = SandboxManager([SandboxPoolConfig(
            language=Language.PYTHON, image=TEST_IMAGES[Language.PYTHON], pool_size=0, running_timeout=120)], client, max_sandboxes=3)
        return holder["manager"]

    settings = ControlSettings(token=TOKEN, handle_ttl_seconds=3, reaper_interval_seconds=0.5)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings, factory), host="127.0.0.1", port=port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", holder["manager"], client
    server.should_exit = True
    thread.join(timeout=60)
    owner = holder["manager"].owner.owner_id
    assert client.containers.list(all=True, filters={"label": [f"{LABEL_OWNER}={owner}"]}) == []
    client.close()


def owned(client, manager):
    # sparse: listing must not inspect each container, which races a concurrent removal.
    return client.containers.list(all=True, sparse=True, filters={"label": [
        f"{LABEL_APP}={APP_LABEL_VALUE}", f"{LABEL_OWNER}={manager.owner.owner_id}"]})


def test_remote_acquire_run_artifact_dispose(service):
    url, manager, client = service
    remote = RemoteSandboxManager(url, token=TOKEN)
    sandbox = remote.get_sandbox(Language.PYTHON)
    try:
        sandbox.prepare_workdir({"main.py": SubmissionFile(
            "main.py", "open('out.txt','w').write(input()); print('done')")})
        result = sandbox.run_process(ProcessRequest.command("python3 main.py", stdin=b"hello\n", timeout=10))
        assert result.stdout.strip() == "done"
        assert sandbox.extract_file("/app/out.txt").content_text == "hello"
        with pytest.raises(ArtifactNotFound):
            sandbox.extract_file("/app/missing.txt")
        assert len(owned(client, manager)) == 1
    finally:
        assert remote.dispose(sandbox) is DisposalStatus.DISPOSED
    assert owned(client, manager) == []
    # Repeated DELETE after a lost response is confirmed by the tombstone.
    repeat = requests.delete(f"{url}/sandboxes/{sandbox.sandbox_id}",
                             headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
    assert repeat.json() == {"status": "already_disposed"}
    remote.shutdown()


def test_replayed_acquire_creates_one_container(service):
    url, manager, client = service
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = {"request_id": "replayed-request-0001"}
    first = requests.post(f"{url}/sandboxes/python", json=body, headers=headers, timeout=60).json()
    second = requests.post(f"{url}/sandboxes/python", json=body, headers=headers, timeout=60).json()
    assert first["sandbox_id"] == second["sandbox_id"]
    assert len(owned(client, manager)) == 1
    assert requests.delete(f"{url}/sandboxes/{first['sandbox_id']}", headers=headers,
                           timeout=30).json()["status"] == "disposed"


def test_abandoned_handle_expires_and_its_container_is_removed(service):
    url, manager, client = service
    remote = RemoteSandboxManager(url, token=TOKEN)
    sandbox = remote.get_sandbox(Language.PYTHON)  # Client "crashes" and never disposes.
    assert len(owned(client, manager)) == 1
    deadline = time.monotonic() + 15
    while owned(client, manager) and time.monotonic() < deadline:
        time.sleep(0.25)
    assert owned(client, manager) == []
    with pytest.raises(SandboxHandleGone):
        sandbox.run_process(ProcessRequest(argv=("echo", "late")))
    sandbox.close()
    remote.shutdown()


def test_unauthenticated_client_cannot_operate(service):
    url, manager, client = service
    assert requests.get(f"{url}/health", timeout=5).status_code == 200
    response = requests.post(f"{url}/sandboxes/python", json={"request_id": "anonymous-0001"}, timeout=5)
    assert response.status_code == 401
    assert owned(client, manager) == []
