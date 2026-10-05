"""Contract checks for Prisma's deliberate execution request and host lifecycle."""

import asyncio
import threading
from unittest.mock import Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.models.sandbox_models import CommandResponse, ResponseCategory
from web.config import auth
from web.main import app
from web.schemas.execution import (
    MAX_OUTPUT_BYTES,
    DeliberateCodeExecutionRequest,
)
from web.service.deliberate_execution_service import execute_code


REQUEST = {
    "language": "python",
    "submission_files": [{"filename": "main.py", "content": "print(input())"}],
    "program_command": "python main.py",
    "test_cases": [["Alice"], ["Bob"]],
    "assets": [],
}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "contract-token")
    monkeypatch.setattr(auth, "integration_auth_config", None)


def command_result(category=ResponseCategory.SUCCESS, stdout="Hello\n", stderr="", exit_code=0):
    return CommandResponse(
        category=category, stdout=stdout, stderr=stderr,
        exit_code=exit_code, execution_time=0.01,
    )


def manager_with_sandbox(*results):
    sandbox = Mock()
    sandbox.run_commands.side_effect = results
    manager = Mock()
    manager.get_sandbox.return_value = sandbox
    return manager, sandbox


async def post(payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/v1/execute", json=payload,
            headers={"Authorization": "Bearer contract-token"},
        )


@pytest.mark.asyncio
async def test_execute_requires_trusted_host_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/execute", json=REQUEST)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_prisma_cases_send_stdin_and_receive_process_details():
    manager, sandbox = manager_with_sandbox(
        command_result(stdout="Alice\n"),
        command_result(category=ResponseCategory.RUNTIME_ERROR, stdout="", stderr="bad input", exit_code=1),
    )
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(REQUEST)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["stopped_early"] is False
    assert data["results"][0] == {
        "category": "success", "stdout": "Alice\n", "stderr": "", "exit_code": 0,
        "execution_time": 0.01, "output": "Alice\n", "error_message": None, "truncated": False,
    }
    assert data["results"][1]["category"] == "runtime_error"
    assert data["results"][1]["stderr"] == "bad input"
    assert data["results"][1]["exit_code"] == 1
    assert sandbox.run_commands.call_args_list[0].args[:2] == (["Alice"], "python main.py")
    assert sandbox.run_commands.call_args_list[1].args[:2] == (["Bob"], "python main.py")
    manager.release_sandbox.assert_called_once()


@pytest.mark.asyncio
async def test_empty_stdin_runs_once_and_output_is_bounded():
    manager, sandbox = manager_with_sandbox()
    sandbox.run_command.return_value = command_result(stdout="é" * MAX_OUTPUT_BYTES, stderr="err")
    payload = {key: value for key, value in REQUEST.items() if key != "test_cases"}
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(payload)
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert len(result["stdout"].encode()) <= MAX_OUTPUT_BYTES
    assert result["truncated"] is True
    sandbox.run_command.assert_called_once()


@pytest.mark.parametrize("change", [
    {"inputs": [["Alice"]]},
    {"test_cases": []},
    {"test_cases": [[]] * 5},
    {"test_cases": [["x" * (16 * 1024 + 1)]]},
    {"submission_files": [{"filename": "../main.py", "content": "x"}]},
    {"submission_files": [{"filename": "main.py", "content": "x"}] * 2},
    {"submission_files": [{"filename": "main.py", "content": "x" * (64 * 1024 + 1)}]},
    {"submission_files": [{"filename": f"file{i}.py", "content": "x"} for i in range(21)]},
    {"submission_files": [{"filename": f"file{i}.py", "content": "x" * (60 * 1024)} for i in range(5)]},
    {"program_command": "python 'unterminated"},
    {"language": "PYTHON"},
    {"assets": [{"source": "../secret", "target": "/tmp/secret"}]},
    {"assets": [{"source": f"asset{i}", "target": f"/tmp/asset{i}"} for i in range(6)]},
])
@pytest.mark.asyncio
async def test_invalid_requests_are_rejected_before_acquisition(change):
    payload = dict(REQUEST)
    payload.update(change)
    with patch("web.service.deliberate_execution_service.get_sandbox_manager") as manager:
        response = await post(payload)
    assert response.status_code == 422
    assert response.json()["detail"]
    manager.assert_not_called()


@pytest.mark.asyncio
async def test_unavailable_manager_and_sandbox_failure_are_service_errors():
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", side_effect=ValueError("not ready")):
        response = await post(REQUEST)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "EXECUTION_UNAVAILABLE"

    manager, sandbox = manager_with_sandbox(command_result(category=ResponseCategory.SYSTEM_ERROR))
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(REQUEST)
    assert response.status_code == 503
    manager.release_sandbox.assert_called_once()

    manager, sandbox = manager_with_sandbox()
    sandbox.prepare_workdir.side_effect = RuntimeError("Docker unavailable")
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(REQUEST)
    assert response.status_code == 503
    assert "Docker unavailable" not in response.text
    manager.release_sandbox.assert_called_once()


@pytest.mark.asyncio
async def test_timeout_stops_batch_and_destroys_sandbox():
    manager, sandbox = manager_with_sandbox(
        command_result(category=ResponseCategory.TIMEOUT, stderr="Execution timed out", exit_code=124)
    )
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(REQUEST)
    assert response.status_code == 200
    assert response.json()["results"][0]["category"] == "timeout"
    assert response.json()["stopped_early"] is True
    assert len(response.json()["results"]) == 1
    manager.destroy_sandbox.assert_called_once()
    manager.release_sandbox.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_erase_known_execution_result():
    manager, _ = manager_with_sandbox(
        command_result(stdout="one"), command_result(stdout="two")
    )
    manager.release_sandbox.side_effect = RuntimeError("release failed")
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        response = await post(REQUEST)
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@pytest.mark.asyncio
async def test_trusted_assets_are_injected_before_execution():
    manager, sandbox = manager_with_sandbox(command_result(), command_result())
    payload = dict(REQUEST, assets=[{
        "source": "datasets/sample.txt", "target": "/tmp/sample.txt", "read_only": True,
    }])
    asset = ResolvedAsset(target="/tmp/sample.txt", content=b"sample", read_only=True)
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager), \
         patch("web.service.deliberate_execution_service.AssetSourceResolver") as resolver:
        resolver.return_value.resolve_assets.return_value = [asset]
        response = await post(payload)
    assert response.status_code == 200
    resolver.return_value.resolve_assets.assert_called_once()
    assert resolver.return_value.resolve_assets.call_args.args[0][0].source == "datasets/sample.txt"
    sandbox.inject_assets.assert_called_once_with([asset])
    calls = [call[0] for call in sandbox.mock_calls]
    assert calls.index("prepare_workdir") < calls.index("inject_assets") < calls.index("run_commands")
    manager.release_sandbox.assert_called_once()


@pytest.mark.asyncio
async def test_deadline_and_disconnect_leave_worker_to_release_sandbox(monkeypatch):
    from web.service import deliberate_execution_service as service

    started, unblock = threading.Event(), threading.Event()
    manager, sandbox = manager_with_sandbox()
    def blocked(*_args, **_kwargs):
        started.set()
        unblock.wait(timeout=2)
        return command_result()
    sandbox.run_commands.side_effect = blocked
    request = DeliberateCodeExecutionRequest.model_validate(REQUEST)
    monkeypatch.setattr(service, "REQUEST_DEADLINE_SECONDS", 0.02)
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        with pytest.raises(service.ExecutionServiceError) as error:
            await execute_code(request)
        assert error.value.code == "EXECUTION_DEADLINE_EXCEEDED"
        assert started.is_set()
        unblock.set()
        await asyncio.to_thread(lambda: None)
        for _ in range(100):
            if manager.release_sandbox.called:
                break
            await asyncio.sleep(0.01)
    manager.release_sandbox.assert_called_once()

    started.clear()
    unblock.clear()
    manager.reset_mock()
    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=manager):
        task = asyncio.create_task(execute_code(request))
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        unblock.set()
        for _ in range(100):
            if manager.release_sandbox.called:
                break
            await asyncio.sleep(0.01)
    manager.release_sandbox.assert_called_once()
