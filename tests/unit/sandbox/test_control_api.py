"""Private control API: token, handle ownership, replay, expiry and error codes."""
import base64
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from sandbox_manager.api import ControlSettings, HandleRegistry, create_app
from sandbox_manager.language_pool import SandboxUnavailableError
from sandbox_manager.models.api_models import MAX_BODY_BYTES, MAX_OUTPUT_BYTES
from sandbox_manager.models.sandbox_models import (
    CommandResponse,
    DisposalStatus,
    ExtractedFile,
    Language,
    ResponseCategory,
    SandboxState,
)
from tests.unit.sandbox.fakes import Clock

TOKEN = "s3cret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSandbox:
    def __init__(self, language):
        self.language = language
        self.state = SandboxState.ACTIVE
        self.files = {}
        self.run_command = Mock(return_value=CommandResponse("out", "", 0, 0.1, ResponseCategory.SUCCESS))
        self.run_commands = Mock(return_value=CommandResponse("batch", "", 0, 0.1, ResponseCategory.SUCCESS))
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
    def __init__(self, scale_limit=3):
        self.language_pools = {Language.PYTHON: SimpleNamespace(config=SimpleNamespace(scale_limit=scale_limit))}
        self.acquired = []
        self.disposed = []
        self.dispose_result = None
        self.dispose_error = None
        self.unavailable = False
        self.shutdown = Mock()

    def get_sandbox(self, language):
        if language not in self.language_pools:
            raise ValueError("unsupported")
        if self.unavailable:
            raise SandboxUnavailableError("busy")
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
                         ("post", "/sandboxes/x/run"), ("get", "/sandboxes/x/files?path=/a")]:
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
    monkeypatch.setenv("SANDBOX_MAX_HANDLES", "7")
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    settings = ControlSettings.from_env()
    assert settings.token == "t" and settings.max_handles == 7 and settings.worker_count == 4
    assert "token='t'" not in repr(settings)


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


def test_max_handles_is_enforced(api, manager):
    for index in range(3):  # Default limit = sum of pool scale limits.
        assert acquire(api, f"request-000{index}").status_code == 200
    response = acquire(api, "request-0009")
    assert response.status_code == 429 and code(response) == "HANDLE_LIMIT"
    handle = acquire(api, "request-0000").json()["sandbox_id"]  # Replay still works.
    api.delete(f"/sandboxes/{handle}", headers=AUTH)
    assert acquire(api, "request-0009").status_code == 200


def test_pool_exhaustion_and_unknown_language(api, manager):
    manager.unavailable = True
    response = acquire(api)
    assert response.status_code == 503 and code(response) == "SANDBOX_UNAVAILABLE"
    response = acquire(api, language="java")
    assert response.status_code == 400 and code(response) == "LANGUAGE_UNAVAILABLE"


# ------------------------------------------------------------------ operations and errors

def test_operations_reach_the_owned_sandbox(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    files = {"main.py": {"filename": "main.py", "content": "print(1)"}}
    assert api.post(f"/sandboxes/{handle}/prepare", json={"submission_files": files}, headers=AUTH).status_code == 200
    asset = {"target": "/tmp/app/x", "content": base64.b64encode(b"data").decode()}
    assert api.post(f"/sandboxes/{handle}/inject", json={"resolved_assets": [asset]}, headers=AUTH).status_code == 200
    run = api.post(f"/sandboxes/{handle}/run", json={"command": "python main.py", "timeout": 5}, headers=AUTH)
    assert run.json()["stdout"] == "out" and run.json()["truncated"] is False
    batch = api.post(f"/sandboxes/{handle}/run-batch", json={"commands": ["1"], "program_command": "p"},
                     headers=AUTH)
    assert batch.json()["stdout"] == "batch"
    sandbox = manager.acquired[0]
    sandbox.prepare_workdir.assert_called_once()
    assert sandbox.inject_assets.call_args.args[0][0].content == b"data"
    sandbox.run_command.assert_called_once_with(command="python main.py", timeout=5, workdir="/app")


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
    manager.acquired[0].run_command.side_effect = RuntimeError("docker exploded: secret detail")
    response = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)
    assert response.status_code == 500 and code(response) == "SANDBOX_ERROR"
    assert "secret" not in response.text


def test_output_is_truncated_at_the_limit(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].run_command.return_value = CommandResponse(
        "x" * (MAX_OUTPUT_BYTES + 10), "", 0, 0.1, ResponseCategory.SUCCESS)
    data = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH).json()
    assert len(data["stdout"]) == MAX_OUTPUT_BYTES and data["truncated"] is True


@pytest.mark.parametrize("payload", [
    {"command": "x", "timeout": 0},
    {"command": "x", "timeout": 10_000},
    {"command": ""},
    {"command": "x" * (64 * 1024 + 1)},
])
def test_command_limits(api, payload):
    handle = acquire(api).json()["sandbox_id"]
    response = api.post(f"/sandboxes/{handle}/run", json=payload, headers=AUTH)
    assert response.status_code == 422 and code(response) == "INVALID_REQUEST"
    assert "xxxx" not in response.text  # Input is not echoed.


def test_batch_and_submission_limits(api):
    handle = acquire(api).json()["sandbox_id"]
    response = api.post(f"/sandboxes/{handle}/run-batch", json={"commands": ["x" * (97 * 1024)]}, headers=AUTH)
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
    response = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)
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
    response = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)
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
    api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)  # Touch.
    clock.now += 45
    assert registry.reap() == 0
    clock.now += 20
    assert registry.reap() == 1
    assert manager.acquired[0].state is SandboxState.DISPOSED
    response = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)
    assert response.status_code == 410 and code(response) == "HANDLE_EXPIRED"
    assert api.delete(f"/sandboxes/{handle}", headers=AUTH).json()["status"] == "already_disposed"


def test_pool_disposed_sandbox_reports_expired_and_is_reaped(api, manager):
    handle = acquire(api).json()["sandbox_id"]
    manager.acquired[0].state = SandboxState.DISPOSED  # Pool running timeout.
    response = api.post(f"/sandboxes/{handle}/run", json={"command": "x"}, headers=AUTH)
    assert response.status_code == 410 and code(response) == "HANDLE_EXPIRED"
    assert api.app.state.registry.reap() == 1
    assert api.app.state.registry.stats()["handles"] == 0


def test_tombstones_are_bounded(manager, clock):
    registry = HandleRegistry(manager, max_handles=100, ttl=60, tombstone_ttl=10, max_tombstones=2, clock=clock)
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
    registry = HandleRegistry(manager, max_handles=10, ttl=5, clock=clock)
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
