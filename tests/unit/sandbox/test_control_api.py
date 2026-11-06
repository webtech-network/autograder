"""Private control API: token, handle ownership, replay, expiry and error codes."""
import base64
import logging
from concurrent.futures import as_completed
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from sandbox_manager.api import ControlSettings, HandleRegistry, create_app
from sandbox_manager.errors import (
    ArtifactReadError, RuntimeUnavailableError, SandboxCapacityTimeout, SandboxInvalidatedError,
    SandboxLifetimeExceeded,
)
from sandbox_manager.language_pool import SandboxUnavailableError
from autograder.models.process import MAX_STDIN_BYTES, ProcessRequest, ProcessResult, ProcessStatus
from sandbox_manager.models.api_models import MAX_BODY_BYTES
from autograder.models.execution import ExtractedFile
from sandbox_manager.models.sandbox_models import DisposalStatus, SandboxState
from autograder.models.language import Language
from tests.unit.sandbox.fakes import Clock

TOKEN = "s3cret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSandbox:
    def __init__(self, language):
        self.language = language
        self.state = SandboxState.ACTIVE
        self.files = {}
        self.run_process = Mock(return_value=ProcessResult(ProcessStatus.EXITED, 0, "out", "", duration=0.1))
        self.prepare_workdir = Mock()
        self.inject_assets = Mock()

    def extract_file(self, path, max_bytes):
        if path not in self.files:
            raise FileNotFoundError(path)
        data = self.files[path]
        if len(data) > max_bytes:
            raise ValueError("File exceeds maximum size")
        return ExtractedFile(path=path, content_bytes=data, size=len(data), content_text=data.decode())


class FakeManager:
    def __init__(self):
        self.language_pools = {Language.PYTHON: SimpleNamespace(config=SimpleNamespace(running_timeout=120))}
        self.acquired = []
        self.disposed = []
        self.dispose_result = None
        self.dispose_error = None
        self.unavailable = False
        self.saturated = False
        self.waits = []
        self.lifetimes = []
        self.shutdown = Mock()

    def get_sandbox(self, language, wait_seconds=0.0, lifetime_seconds=None):
        self.waits.append(wait_seconds)
        self.lifetimes.append(lifetime_seconds)
        if lifetime_seconds is not None and lifetime_seconds > 120:
            raise SandboxLifetimeExceeded("longer than running_timeout")
        if language not in self.language_pools:
            raise RuntimeUnavailableError("no runtime")
        if self.unavailable:
            raise SandboxUnavailableError("shut down")
        if self.saturated:
            raise SandboxCapacityTimeout("full")
        sandbox = FakeSandbox(language)
        self.acquired.append(sandbox)
        return sandbox

    def dispose(self, sandbox):
        self.disposed.append(sandbox)
        if self.dispose_error is not None:
            error, self.dispose_error = self.dispose_error, None
            raise error
        if self.dispose_result is not None:
            return self.dispose_result
        if sandbox.state is SandboxState.DISPOSED:
            return DisposalStatus.ALREADY_DISPOSED
        sandbox.state = SandboxState.DISPOSED
        return DisposalStatus.DISPOSED

    def get_pool_stats(self):
        return {"python": {"quarantined": 0}}

    def get_budget_stats(self):
        return {"max_sandboxes": 3, "held": len(self.acquired) - len(self.disposed), "waiting": 0}


@pytest.fixture
def manager():
    return FakeManager()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def api(manager, clock):
    settings = ControlSettings(token=TOKEN, handle_ttl_seconds=60, tombstone_seconds=600,
                               reaper_interval_seconds=3600)
    with TestClient(create_app(settings, lambda: manager, clock=clock)) as client:
        yield client
    manager.shutdown.assert_called_once()


def acquire(api, request_id="request-0001", language="python"):
    return api.post(f"/sandboxes/{language}", json={"request_id": request_id}, headers=AUTH)


def code(response):
    return response.json()["detail"]["code"]


# ------------------------------------------------------------------ token

def test_health_is_public_and_everything_else_needs_the_token(api):
    assert api.get("/health").json() == {"status": "ok"}
    for method, path in [("get", "/stats"), ("post", "/sandboxes/python"), ("delete", "/sandboxes/x"),
                         ("post", "/sandboxes/x/process"), ("get", "/sandboxes/x/files?path=/a")]:
        response = getattr(api, method)(path)
        assert response.status_code == 401, path
        assert code(response) == "UNAUTHORIZED"
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Bearer wrong", "Basic " + TOKEN, TOKEN, "Bearer", ""])
def test_bad_tokens_are_rejected(api, manager, header):
    response = api.post("/sandboxes/python", json={"request_id": "request-0001"},
                        headers={"Authorization": header})
    assert response.status_code == 401
    assert manager.acquired == []


def test_valid_token_is_accepted(api):
    assert api.get("/stats", headers=AUTH).status_code == 200


def test_refuses_to_start_without_token(manager):
    with pytest.raises(RuntimeError, match="SANDBOX_API_TOKEN is required"):
        with TestClient(create_app(ControlSettings(), lambda: manager)):
            pass


def test_explicit_unauthenticated_development_mode_warns(manager, caplog):
    settings = ControlSettings(allow_unauthenticated=True, reaper_interval_seconds=3600)
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(settings, lambda: manager)) as client:
            assert client.post("/sandboxes/python", json={"request_id": "request-0001"}).status_code == 200
    assert "UNAUTHENTICATED" in caplog.text


def test_refuses_multiple_workers(manager):
    with pytest.raises(RuntimeError, match="one worker"):
        with TestClient(create_app(ControlSettings(token=TOKEN, worker_count=2), lambda: manager)):
            pass


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("SANDBOX_API_TOKEN", "t")
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    settings = ControlSettings.from_env()
    assert settings.token == "t" and settings.worker_count == 4
    assert "token='t'" not in repr(settings)


def test_removed_handle_limit_setting_is_rejected_at_startup(monkeypatch):
    monkeypatch.setenv("SANDBOX_API_TOKEN", "t")
    monkeypatch.setenv("SANDBOX_MAX_HANDLES", "7")
    with pytest.raises(RuntimeError, match="SANDBOX_MAX_HANDLES was removed.*max_sandboxes"):
        ControlSettings.from_env()


@pytest.mark.parametrize(("variable", "value", "message"), [
    ("SANDBOX_HANDLE_TTL_SECONDS", "ten", "SANDBOX_HANDLE_TTL_SECONDS must be a number, got 'ten'"),
    ("WEB_CONCURRENCY", "1.5", "WEB_CONCURRENCY must be an integer, got '1.5'"),
])
def test_malformed_setting_is_rejected_naming_the_variable(monkeypatch, variable, value, message):
    monkeypatch.setenv(variable, value)
    with pytest.raises(RuntimeError, match=message):
        ControlSettings.from_env()


def test_sandbox_configuration_file_is_a_validated_startup_setting(monkeypatch, tmp_path):
    # Read with the other settings, and a missing file stops startup before Docker is touched.
    monkeypatch.setenv("SANDBOX_API_TOKEN", "t")
    monkeypatch.setenv("SANDBOX_CONFIG_FILE", str(tmp_path / "missing.yml"))
    settings = ControlSettings.from_env()
    assert settings.config_file == str(tmp_path / "missing.yml")
    with pytest.raises(FileNotFoundError, match="missing.yml"):
        with TestClient(create_app(settings)):
            pass


# ------------------------------------------------------------------ handles

def test_handles_are_random_and_not_container_ids(api, manager):
    first = acquire(api, "request-0001").json()["sandbox_id"]
    second = acquire(api, "request-0002").json()["sandbox_id"]
    assert first != second and len(first) >= 32
    assert len(manager.acquired) == 2


def test_replayed_acquire_returns_the_same_handle(api, manager):
    first = acquire(api, "lost-response-1")
    second = acquire(api, "lost-response-1")
    assert first.status_code == second.status_code == 200
    assert first.json()["sandbox_id"] == second.json()["sandbox_id"]
    assert len(manager.acquired) == 1


def test_request_id_reuse_for_other_language_conflicts(api, manager):
    manager.language_pools[Language.JAVA] = manager.language_pools[Language.PYTHON]
    acquire(api, "request-0001")
    response = acquire(api, "request-0001", "java")
    assert response.status_code == 409 and code(response) == "REQUEST_ID_CONFLICT"


def test_replay_after_close_does_not_create_a_second_container(api, manager):
    handle = acquire(api, "request-0001").json()["sandbox_id"]
    api.delete(f"/sandboxes/{handle}", headers=AUTH)
    response = acquire(api, "request-0001")
    assert response.status_code == 410 and code(response) == "HANDLE_CLOSED"
    assert len(manager.acquired) == 1


def test_request_id_is_required_and_validated(api):
    assert api.post("/sandboxes/python", json={}, headers=AUTH).status_code == 422
    assert api.post("/sandboxes/python", json={"request_id": "x"}, headers=AUTH).status_code == 422


def test_acquire_passes_the_requested_wait_and_reports_capacity_timeout(api, manager):
    response = api.post("/sandboxes/python", json={"request_id": "request-0001", "wait_seconds": 12.5}, headers=AUTH)
    assert response.status_code == 200 and manager.waits == [12.5]
    manager.saturated = True
    response = acquire(api, "request-0002")
    assert response.status_code == 503 and code(response) == "CAPACITY_TIMEOUT"
    assert manager.waits == [12.5, 0.0]
    manager.saturated = False
    assert acquire(api, "request-0002").status_code == 200  # A failed attempt is not remembered.
    for wait in (-1, 901):
        response = api.post("/sandboxes/python", json={"request_id": "request-0003", "wait_seconds": wait},
                            headers=AUTH)
        assert response.status_code == 422 and code(response) == "INVALID_REQUEST"


def test_acquire_forwards_the_lifetime_and_refuses_one_beyond_the_host_maximum(api, manager):
    response = api.post("/sandboxes/python", json={"request_id": "request-0001", "lifetime_seconds": 92.5},
                        headers=AUTH)
    assert response.status_code == 200
    response = api.post("/sandboxes/python", json={"request_id": "request-0002", "lifetime_seconds": 121},
                        headers=AUTH)
    assert response.status_code == 422 and code(response) == "LIFETIME_EXCEEDED"
    assert acquire(api, "request-0003").status_code == 200  # omitted: the host's running_timeout
    assert manager.lifetimes == [92.5, 121, None] and len(manager.acquired) == 2
    for lifetime in (0, -1, "inf"):
        response = api.post("/sandboxes/python", json={"request_id": "request-0004", "lifetime_seconds": lifetime},
                            headers=AUTH)
        assert response.status_code == 422 and code(response) == "INVALID_REQUEST"


def test_pool_exhaustion_and_unknown_language(api, manager):
    manager.unavailable = True
    response = acquire(api)
    assert response.status_code == 503 and code(response) == "SANDBOX_UNAVAILABLE"
    response = acquire(api, language="java")
    assert response.status_code == 501 and code(response) == "RUNTIME_UNAVAILABLE"
    response = acquire(api, language="rust")
    assert response.status_code == 422 and code(response) == "INVALID_REQUEST"


# ------------------------------------------------------------------ operations and errors

def test_operations_reach_the_owned_sandbox(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    files = {"main.py": {"filename": "main.py", "content": "print(1)"}}
    assert api.post(f"/sandboxes/{handle}/prepare", json={"submission_files": files}, headers=AUTH).status_code == 200
    asset = {"target": "/tmp/app/x", "content": base64.b64encode(b"data").decode()}
    assert api.post(f"/sandboxes/{handle}/inject", json={"resolved_assets": [asset]}, headers=AUTH).status_code == 200
    run = api.post(f"/sandboxes/{handle}/process", headers=AUTH, json={
        "argv": ["python", "main.py"], "stdin": base64.b64encode(b"1\n").decode(), "timeout": 5})
    assert run.json() == {"status": "exited", "exit_code": 0, "stdout": "out", "stderr": "",
                          "stdout_truncated": False, "stderr_truncated": False, "duration": 0.1,
                          "missing_executable": None}
    sandbox = manager.acquired[0]
    sandbox.prepare_workdir.assert_called_once()
    assert sandbox.inject_assets.call_args.args[0][0].content == b"data"
    sandbox.run_process.assert_called_once_with(ProcessRequest(argv=("python", "main.py"), stdin=b"1\n", timeout=5))


def test_unknown_handle_and_missing_artifact_are_distinct(api, manager):
    response = api.get("/sandboxes/not-a-handle/files", params={"path": "/app/out.txt"}, headers=AUTH)
    assert response.status_code == 404 and code(response) == "HANDLE_NOT_FOUND"
    handle = acquire(api).json()["sandbox_id"]
    response = api.get(f"/sandboxes/{handle}/files", params={"path": "/app/out.txt"}, headers=AUTH)
    assert response.status_code == 404 and code(response) == "ARTIFACT_NOT_FOUND"
    manager.acquired[0].files["/app/out.txt"] = b"hello"
    response = api.get(f"/sandboxes/{handle}/files", params={"path": "/app/out.txt"}, headers=AUTH)
    assert base64.b64decode(response.json()["content_bytes"]) == b"hello"


def test_artifact_size_is_bounded(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    response = api.get(f"/sandboxes/{handle}/files", params={"path": "/a", "max_bytes": 2 ** 30}, headers=AUTH)
    assert response.status_code == 422
    manager.acquired[0].files["/a"] = b"12345"
    response = api.get(f"/sandboxes/{handle}/files", params={"path": "/a", "max_bytes": 2}, headers=AUTH)
    assert response.status_code == 422 and code(response) == "ARTIFACT_INVALID"


def test_execution_failure_is_a_sandbox_error(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].run_process.side_effect = RuntimeError("docker exploded: secret detail")
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 500 and code(response) == "SANDBOX_ERROR"
    assert "secret" not in response.text


def test_invalidated_sandbox_and_failed_readback_are_distinct_errors(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    sandbox = manager.acquired[0]
    sandbox.run_process.side_effect = SandboxInvalidatedError("survivors")
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 409 and code(response) == "SANDBOX_INVALIDATED"
    sandbox.extract_file = Mock(side_effect=ArtifactReadError("short read"))
    response = api.get(f"/sandboxes/{handle}/files", params={"path": "/app/out.txt"}, headers=AUTH)
    assert response.status_code == 500 and code(response) == "ARTIFACT_READ_FAILED"
    assert "short read" not in response.text


def test_exhausted_sandbox_is_a_distinct_student_outcome(api, manager):
    from autograder.models.process import SandboxExhausted
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].run_process.side_effect = SandboxExhausted("limit")
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 409 and code(response) == "SANDBOX_EXHAUSTED"


def test_output_bound_is_forwarded_and_truncation_reported(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].run_process.return_value = ProcessResult(
        ProcessStatus.EXITED, 0, "x" * 16, "", stdout_truncated=True)
    data = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"], "max_output_bytes": 16},
                    headers=AUTH).json()
    assert data["stdout"] == "x" * 16 and data["stdout_truncated"] is True
    assert manager.acquired[0].run_process.call_args.args[0].max_output_bytes == 16


@pytest.mark.parametrize("payload", [
    {"argv": ["x"], "timeout": 0},
    {"argv": ["x"], "timeout": 10_000},
    {"argv": ["x"], "timeout": 121},                 # above the pool's running_timeout lease
    {"argv": []},
    {"argv": [""]},
    {"argv": ["x"], "shell": "x"},                   # exactly one command mode
    {},
    {"shell": "   "},
    {"argv": ["x" * (64 * 1024 + 1)]},
    {"argv": ["x"], "cwd": "app"},
    {"argv": ["x"], "cwd": "/app/../etc"},
    {"argv": ["x"], "stdin": "not base64!"},
    {"argv": ["x"], "max_output_bytes": 0},
    {"argv": ["x"], "workdir": "/app"},              # unknown fields are rejected
])
def test_process_limits(api, payload):
    handle = acquire(api).json()["sandbox_id"]
    response = api.post(f"/sandboxes/{handle}/process", json=payload, headers=AUTH)
    assert response.status_code == 422 and code(response) == "INVALID_REQUEST"
    assert "xxxx" not in response.text  # Input is not echoed.


def test_stdin_and_submission_limits(api):
    handle = acquire(api).json()["sandbox_id"]
    stdin = base64.b64encode(b"x" * (MAX_STDIN_BYTES + 1)).decode()
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["cat"], "stdin": stdin}, headers=AUTH)
    assert response.status_code == 422
    files = {str(i): {"filename": str(i), "content": ""} for i in range(101)}
    assert api.post(f"/sandboxes/{handle}/prepare", json={"submission_files": files},
                    headers=AUTH).status_code == 422


def test_body_limit(api):
    response = api.post("/sandboxes/python", content=b"{" + b" " * MAX_BODY_BYTES + b"}",
                        headers={**AUTH, "Content-Type": "application/json"})
    assert response.status_code == 413 and code(response) == "REQUEST_TOO_LARGE"


# ------------------------------------------------------------------ disposal

def test_delete_disposes_then_forgets_and_repeats_succeed(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    first = api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert first.status_code == 200 and first.json() == {"status": "disposed"}
    second = api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert second.status_code == 200 and second.json() == {"status": "already_disposed"}
    assert len(manager.disposed) == 1
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 410 and code(response) == "HANDLE_CLOSED"


def test_unknown_delete_is_404(api):
    response = api.delete("/sandboxes/never-issued", headers=AUTH)
    assert response.status_code == 404 and code(response) == "HANDLE_NOT_FOUND"


def test_delete_failure_keeps_a_closing_record_for_retry(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.dispose_error = RuntimeError("daemon")
    response = api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert response.status_code == 500 and code(response) == "DISPOSAL_FAILED"
    assert api.get("/stats", headers=AUTH).json()["handles"]["closing"] == 1
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 410  # Closing: no new work.
    retry = api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert retry.status_code == 200 and retry.json()["status"] == "disposed"
    assert len(manager.disposed) == 2


def test_quarantined_disposal_transfers_the_record_to_the_pool(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.dispose_result = DisposalStatus.QUARANTINED
    response = api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert response.status_code == 200 and response.json()["status"] == "quarantined"
    assert api.get("/stats", headers=AUTH).json()["handles"]["handles"] == 0


def test_idle_handles_expire_through_the_reaper(api, manager, clock):
    handle = acquire(api).json()["sandbox_id"]
    registry = api.app.state.registry
    clock.now += 30
    api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)  # Touch.
    clock.now += 45
    assert registry.reap() == 0
    clock.now += 20
    assert registry.reap() == 1
    assert manager.acquired[0].state is SandboxState.DISPOSED
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 410 and code(response) == "HANDLE_EXPIRED"
    assert api.delete(f"/sandboxes/{handle}", headers=AUTH).json()["status"] == "already_disposed"


def test_pool_disposed_sandbox_reports_expired_and_is_reaped(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].state = SandboxState.DISPOSED  # Pool running timeout.
    response = api.post(f"/sandboxes/{handle}/process", json={"argv": ["x"]}, headers=AUTH)
    assert response.status_code == 410 and code(response) == "HANDLE_EXPIRED"
    assert api.app.state.registry.reap() == 1
    assert api.app.state.registry.stats()["handles"] == 0


def test_tombstones_are_bounded(manager, clock):
    registry = HandleRegistry(manager, ttl=60, tombstone_ttl=10, max_tombstones=2, clock=clock)
    handles = [registry.acquire(Language.PYTHON, f"request-{i:04d}") for i in range(4)]
    for handle in handles:
        registry.close(handle.handle_id)
    assert registry.stats()["tombstones"] == 2
    with pytest.raises(Exception) as error:
        registry.close(handles[0].handle_id)
    assert error.value.code == "HANDLE_NOT_FOUND"
    clock.now += 11
    registry.reap()
    assert registry.stats()["tombstones"] == 0


def test_in_flight_handles_are_not_reaped(manager, clock):
    registry = HandleRegistry(manager, ttl=5, clock=clock)
    handle = registry.acquire(Language.PYTHON, "request-0001")
    with registry.use(handle.handle_id):
        clock.now += 100
        assert registry.reap() == 0
    clock.now += 6
    assert registry.reap() == 1


def test_shutdown_forgets_handles_and_shuts_manager_down(manager, clock):
    settings = ControlSettings(token=TOKEN, reaper_interval_seconds=3600)
    app = create_app(settings, lambda: manager, clock=clock)
    with TestClient(app) as client:
        acquire(client)
    manager.shutdown.assert_called_once()
    assert app.state.registry.stats()["handles"] == 0


# ------------------------------------------------------------------ waiting on the real budget

@pytest.fixture
def budget_api():
    """The control API over a real manager (fake Docker) with a one-sandbox budget."""
    from concurrent.futures import ThreadPoolExecutor
    from sandbox_manager.manager import SandboxManager
    from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config

    docker_client = FakeDocker()
    real = SandboxManager([pool_config()], docker_client, runtime="runc", max_sandboxes=1, owner=owner(), reclaim_orphans=False,
                          monitor_interval=3600)
    settings = ControlSettings(token=TOKEN, reaper_interval_seconds=3600)
    with TestClient(create_app(settings, lambda: real)) as client, ThreadPoolExecutor(64) as executor:
        yield client, real, docker_client, executor
    assert docker_client.live == {}


def wait_for_waiters(manager, count):
    with manager.budget.condition:
        assert manager.budget.condition.wait_for(lambda: len(manager.budget._waiters) == count, timeout=30)  # pylint: disable=protected-access


def waiting_acquire(client, request_id, wait_seconds=30):
    return client.post("/sandboxes/python", json={"request_id": request_id, "wait_seconds": wait_seconds},
                       headers=AUTH)


def test_waiting_acquisitions_never_starve_the_delete_that_frees_a_slot(budget_api):
    """More waiters than the route threadpool (40) still leave DELETE and /stats responsive."""
    client, real, _, executor = budget_api
    first = acquire(client, "request-holder").json()["sandbox_id"]
    waiters = [executor.submit(waiting_acquire, client, f"request-{index:04d}") for index in range(45)]
    wait_for_waiters(real, 45)
    assert client.get("/stats", headers=AUTH).json()["budget"] == {"max_sandboxes": 1, "held": 1, "waiting": 45}
    assert client.delete(f"/sandboxes/{first}", headers=AUTH).json() == {"status": "disposed"}
    served = 0
    pending = set(waiters)
    while pending:  # Each grant is released again, so every waiter is served in turn.
        done = next(as_completed(pending, timeout=30))
        pending.discard(done)
        response = done.result()
        assert response.status_code == 200, response.text
        assert client.delete(f"/sandboxes/{response.json()['sandbox_id']}", headers=AUTH).status_code == 200
        served += 1
    assert served == 45


def test_a_replay_of_a_waiting_acquisition_gets_the_same_handle(budget_api):
    client, real, docker_client, executor = budget_api
    first = acquire(client, "request-holder").json()["sandbox_id"]
    original = executor.submit(waiting_acquire, client, "request-replayed")
    wait_for_waiters(real, 1)
    replay = executor.submit(waiting_acquire, client, "request-replayed")  # Lost-response retry meanwhile.
    client.delete(f"/sandboxes/{first}", headers=AUTH)
    handles = {original.result(timeout=30).json()["sandbox_id"], replay.result(timeout=30).json()["sandbox_id"]}
    assert len(handles) == 1 and len(docker_client.live) == 1  # One container for one request id.
    client.delete(f"/sandboxes/{handles.pop()}", headers=AUTH)


def test_capacity_timeout_is_a_defined_503_and_leaves_no_handle(budget_api):
    client, _, _, _ = budget_api
    first = acquire(client, "request-holder").json()["sandbox_id"]
    response = waiting_acquire(client, "request-starved", 0.05)
    assert response.status_code == 503 and code(response) == "CAPACITY_TIMEOUT"
    assert client.get("/stats", headers=AUTH).json()["handles"]["handles"] == 1
    client.delete(f"/sandboxes/{first}", headers=AUTH)
    assert waiting_acquire(client, "request-starved", 0).status_code == 200  # Not remembered as failed.
    assert client.get("/stats", headers=AUTH).json()["budget"]["held"] == 1
    for handle in list(client.app.state.registry._handles):  # pylint: disable=protected-access
        client.delete(f"/sandboxes/{handle}", headers=AUTH)


def test_acquisitions_are_not_serialized_by_the_registry():
    """Two cold acquisitions are inside Docker create at the same time."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from sandbox_manager.manager import SandboxManager
    from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config

    docker_client = FakeDocker(gvisor=True)
    together = threading.Barrier(2, timeout=30)
    docker_client.on_run = lambda _kwargs: together.wait()
    real = SandboxManager([pool_config()], docker_client, runtime="runc", max_sandboxes=2, owner=owner(), reclaim_orphans=False,
                          monitor_interval=3600)
    with TestClient(create_app(ControlSettings(token=TOKEN, reaper_interval_seconds=3600), lambda: real)) as client:
        with ThreadPoolExecutor(2) as executor:
            responses = list(executor.map(lambda i: acquire(client, f"request-{i:04d}"), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert docker_client.live == {}
