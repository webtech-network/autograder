"""The real client against the real control API, and cleanup trouble after a grade."""
import socket
import threading
import time

import docker
import pytest
import uvicorn

from autograder import evaluate_submission
from autograder.models.capabilities import HostCapabilities
from autograder.models.process import ProcessRequest, ProcessStatus
from execution_host.docker import DockerSession
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.sandbox_models import DisposalStatus
from autograder.models.language import Language
from sandbox_manager.remote_client import (
    ArtifactNotFound,
    RemoteSandboxError,
    RemoteSandboxManager,
    SandboxHandleGone,
    SandboxHandleNotFound,
)
from tests.unit.pipeline.test_host_capabilities import definition, session, submission
from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config
from tests.unit.sandbox.test_control_api import FakeManager


@pytest.fixture
def served():
    manager = FakeManager()
    app = create_app(ControlSettings(token="wire-token", reaper_interval_seconds=3600), lambda: manager)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    yield f"http://127.0.0.1:{port}", manager
    server.should_exit = True
    thread.join(timeout=10)


def test_client_and_server_agree_on_the_wire(served):
    url, manager = served
    client = RemoteSandboxManager(url, token="wire-token")
    sandbox = client.get_sandbox(Language.PYTHON)
    sandbox.prepare_workdir({})
    result = sandbox.run_process(ProcessRequest(argv=("echo",), stdin=b"a\nb", timeout=2))
    assert (result.status, result.exit_code, result.stdout) == (ProcessStatus.EXITED, 0, "out")
    assert manager.acquired[0].run_process.call_args.args[0] == ProcessRequest(argv=("echo",), stdin=b"a\nb",
                                                                               timeout=2)
    with pytest.raises(ArtifactNotFound):
        sandbox.extract_file("/app/missing.txt")
    manager.acquired[0].files["/app/out.txt"] = b"data"
    assert sandbox.extract_file("/app/out.txt").content_bytes == b"data"
    assert client.dispose(sandbox) is DisposalStatus.DISPOSED
    with pytest.raises(SandboxHandleGone):
        sandbox.run_process(ProcessRequest(argv=("echo",)))
    stranger = type(sandbox)("never-issued", Language.PYTHON, url, token="wire-token")
    with pytest.raises(SandboxHandleNotFound):
        stranger.extract_file("/app/out.txt")
    with pytest.raises(SandboxHandleNotFound):
        client.dispose(stranger)
    unauthenticated = RemoteSandboxManager(url)
    with pytest.raises(RemoteSandboxError) as caught:
        unauthenticated.get_sandbox(Language.PYTHON)
    assert caught.value.status_code == 401
    assert client.get_pool_stats()["handles"]["handles"] == 0
    client.shutdown()


def test_unconfirmed_local_disposal_keeps_the_completed_grade(caplog):
    client = FakeDocker()
    manager = SandboxManager([pool_config()], client, runtime="runc", max_sandboxes=2, owner=owner(), monitor_interval=60)
    events = []
    concrete = {}

    def acquire(language):
        docker_session = DockerSession(manager, language)
        concrete["sandbox"] = docker_session.sandbox
        docker_session.sandbox.container_ref.remove_failures = [docker.errors.APIError("stuck")]
        # Commands are not under test: delegate execution to a scripted session.
        scripted = session()
        docker_session.run_process = scripted.run_process
        docker_session.prepare_workdir = scripted.prepare_workdir
        return docker_session

    try:
        value = definition(preparation={"languages": {"python": {
            "setup_commands": [{"name": "prepare", "command": "prepare"}]}}})
        outcome = evaluate_submission(submission(), definition=value,
                                      capabilities=HostCapabilities(execution=acquire), observer=events.append)
        assert outcome.status == "completed" and outcome.score == 100
        assert events[-1].operation == "close_session" and events[-1].error.code == "CLEANUP_ERROR"
        assert "Execution session cleanup failed" in caplog.text
        stats = manager.get_pool_stats()["python"]
        assert stats["quarantined"] == 1  # The host still sees and retries the trouble.
        assert manager.dispose(concrete["sandbox"]) is DisposalStatus.QUARANTINED
    finally:
        manager.shutdown()
    assert client.live == {}  # Shutdown's final attempt succeeds once Docker recovers.
