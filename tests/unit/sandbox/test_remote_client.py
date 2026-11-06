"""Remote client: replay policy, session ownership and error mapping."""
import base64
import json
from unittest.mock import Mock

import pytest
import requests

from autograder.models.capabilities import ExecutionBudget
from autograder.models.evaluation_error import EvaluationError
from execution_host.docker import DockerSession
from autograder.models.process import ProcessRequest, ProcessStatus, SandboxExhausted
from sandbox_manager.errors import (
    ArtifactReadError, RuntimeUnavailableError, SandboxCapacityTimeout, SandboxInvalidatedError,
    SandboxLifetimeExceeded,
)
from sandbox_manager.models.api_models import TRANSPORT_MARGIN_SECONDS
from sandbox_manager.models.sandbox_models import DisposalStatus
from autograder.models.language import Language
from sandbox_manager.remote_client import (
    ACQUIRE_TIMEOUT_SECONDS,
    ArtifactNotFound,
    RemoteSandboxContainer,
    RemoteSandboxError,
    RemoteSandboxManager,
    SandboxHandleGone,
    SandboxHandleNotFound,
    SandboxUnavailable,
)


def response(status=200, body=None):
    value = requests.Response()
    value.status_code = status
    value._content = json.dumps(body if body is not None else {}).encode()  # pylint: disable=protected-access
    value.reason = "reason"
    return value


def error(status, code):
    return response(status, {"detail": {"code": code, "message": "m"}})


def acquired(sandbox_id="handle-1"):
    return response(200, {"sandbox_id": sandbox_id, "request_id": "r" * 32, "expires_in": 600})


@pytest.fixture
def manager():
    return RemoteSandboxManager("http://sandbox:8001/", token="tok")


def test_token_is_sent_by_manager_and_handles(manager):
    manager._session.post = Mock(return_value=acquired())  # pylint: disable=protected-access
    sandbox = manager.get_sandbox(Language.PYTHON)
    assert manager._session.headers["Authorization"] == "Bearer tok"  # pylint: disable=protected-access
    assert sandbox._session.headers["Authorization"] == "Bearer tok"  # pylint: disable=protected-access
    assert sandbox.sandbox_id == "handle-1" and sandbox.api_url == "http://sandbox:8001"


def test_transport_adapter_never_retries_by_itself(manager):
    adapter = manager._session.get_adapter("http://sandbox")  # pylint: disable=protected-access
    assert adapter.max_retries.total == 0


def test_acquire_replays_with_the_same_request_id_after_lost_response(manager):
    post = Mock(side_effect=[requests.ReadTimeout("lost"), requests.ConnectionError("reset"), acquired()])
    manager._session.post = post  # pylint: disable=protected-access
    sandbox = manager.get_sandbox(Language.JAVA)
    request_ids = {call.kwargs["json"]["request_id"] for call in post.call_args_list}
    assert len(post.call_args_list) == 3 and len(request_ids) == 1
    assert post.call_args.args[0] == "http://sandbox:8001/sandboxes/java"
    assert sandbox.language is Language.JAVA


def test_acquire_gives_up_after_bounded_attempts(manager):
    manager._session.post = Mock(side_effect=requests.ConnectionError("down"))  # pylint: disable=protected-access
    with pytest.raises(RemoteSandboxError) as caught:
        manager.get_sandbox(Language.PYTHON)
    assert caught.value.code == "TRANSPORT_ERROR"
    assert manager._session.post.call_count == 3  # pylint: disable=protected-access


def test_acquire_http_errors_are_not_retried(manager):
    manager._session.post = Mock(return_value=error(503, "SANDBOX_UNAVAILABLE"))  # pylint: disable=protected-access
    with pytest.raises(SandboxUnavailable):
        manager.get_sandbox(Language.PYTHON)
    assert manager._session.post.call_count == 1  # pylint: disable=protected-access


def test_acquire_lets_the_service_wait_for_a_budget_slot(manager):
    manager._session.post = Mock(return_value=acquired())  # pylint: disable=protected-access
    manager.get_sandbox(Language.PYTHON, wait_seconds=600)
    call = manager._session.post.call_args  # pylint: disable=protected-access
    assert call.kwargs["json"]["wait_seconds"] == 600
    assert call.kwargs["timeout"][1] == 600 + ACQUIRE_TIMEOUT_SECONDS  # The read deadline covers the wait.


def test_capacity_timeout_raises_the_local_capacity_error(manager):
    manager._session.post = Mock(return_value=error(503, "CAPACITY_TIMEOUT"))  # pylint: disable=protected-access
    with pytest.raises(SandboxCapacityTimeout):
        manager.get_sandbox(Language.PYTHON, wait_seconds=1)
    assert manager._session.post.call_count == 1  # pylint: disable=protected-access


def test_missing_runtime_raises_the_local_capability_error(manager):
    manager._session.post = Mock(return_value=error(501, "RUNTIME_UNAVAILABLE"))  # pylint: disable=protected-access
    with pytest.raises(RuntimeUnavailableError):
        manager.get_sandbox(Language.C)
    assert manager._session.post.call_count == 1  # pylint: disable=protected-access


def test_acquire_sends_the_lifetime_and_maps_its_refusal_to_the_local_error(manager):
    manager._session.post = Mock(return_value=acquired())  # pylint: disable=protected-access
    manager.get_sandbox(Language.PYTHON, lifetime_seconds=92.5)
    assert manager._session.post.call_args.kwargs["json"]["lifetime_seconds"] == 92.5  # pylint: disable=protected-access
    manager._session.post = Mock(return_value=error(422, "LIFETIME_EXCEEDED"))  # pylint: disable=protected-access
    with pytest.raises(SandboxLifetimeExceeded):
        manager.get_sandbox(Language.PYTHON, lifetime_seconds=10_000)
    assert manager._session.post.call_count == 1  # pylint: disable=protected-access


def test_a_refused_budget_is_the_non_retryable_engine_code():
    refusing = Mock()
    refusing.get_sandbox.side_effect = SandboxLifetimeExceeded("too long")
    with pytest.raises(EvaluationError) as raised:
        DockerSession(refusing, Language.PYTHON, ExecutionBudget(900.0, 30))
    assert (raised.value.code, raised.value.retryable) == ("EXECUTION_BUDGET_EXCEEDED", False)
    assert refusing.get_sandbox.call_args.kwargs["lifetime_seconds"] == ExecutionBudget(900.0, 30).session_seconds


def handle(manager):
    sandbox = RemoteSandboxContainer("handle-1", Language.PYTHON, manager.api_url, token="tok")
    sandbox._session = Mock(wraps=sandbox._session)  # pylint: disable=protected-access
    return sandbox


def test_dispose_returns_status_and_closes_session(manager):
    sandbox = handle(manager)
    manager._session.delete = Mock(return_value=response(200, {"status": "disposed"}))  # pylint: disable=protected-access
    assert manager.dispose(sandbox) is DisposalStatus.DISPOSED
    sandbox._session.close.assert_called_once()  # pylint: disable=protected-access
    assert manager.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
    assert manager._session.delete.call_count == 1  # pylint: disable=protected-access


def test_dispose_closes_session_when_deletion_fails(manager):
    sandbox = handle(manager)
    manager._session.delete = Mock(return_value=error(500, "DISPOSAL_FAILED"))  # pylint: disable=protected-access
    with pytest.raises(RemoteSandboxError):
        manager.dispose(sandbox)
    sandbox._session.close.assert_called_once()  # pylint: disable=protected-access


def test_dispose_closes_session_when_transport_fails(manager):
    sandbox = handle(manager)
    manager._session.delete = Mock(side_effect=requests.ConnectionError("down"))  # pylint: disable=protected-access
    with pytest.raises(RemoteSandboxError):
        manager.dispose(sandbox)
    assert manager._session.delete.call_count == 3  # pylint: disable=protected-access
    sandbox._session.close.assert_called_once()  # pylint: disable=protected-access


def test_dispose_retry_after_lost_response_is_confirmed_by_tombstone(manager):
    sandbox = handle(manager)
    manager._session.delete = Mock(side_effect=[  # pylint: disable=protected-access
        requests.ReadTimeout("lost"), response(200, {"status": "already_disposed"})])
    assert manager.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED


def test_unknown_handle_on_dispose_is_not_a_missing_file(manager):
    sandbox = handle(manager)
    manager._session.delete = Mock(return_value=error(404, "HANDLE_NOT_FOUND"))  # pylint: disable=protected-access
    with pytest.raises(SandboxHandleNotFound) as caught:
        manager.dispose(sandbox)
    assert not isinstance(caught.value, FileNotFoundError)


def test_process_is_never_replayed(manager):
    sandbox = handle(manager)
    sandbox._session.request = Mock(side_effect=requests.ReadTimeout("lost"))  # pylint: disable=protected-access
    with pytest.raises(RemoteSandboxError) as caught:
        sandbox.run_process(ProcessRequest.command("python main.py", timeout=7))
    assert caught.value.code == "TRANSPORT_ERROR"  # an unknown outcome, never a student result
    sandbox._session.request.assert_called_once()  # pylint: disable=protected-access
    assert sandbox._session.request.call_args.kwargs["timeout"] == (5, 7 + TRANSPORT_MARGIN_SECONDS)  # pylint: disable=protected-access
    sandbox._session.request = Mock(side_effect=requests.ConnectionError("x"))  # pylint: disable=protected-access
    with pytest.raises(RemoteSandboxError):
        sandbox.run_process(ProcessRequest(shell="echo 1", timeout=3))
    sandbox._session.request.assert_called_once()  # pylint: disable=protected-access


def test_process_request_and_result_use_the_shared_wire_contract(manager):
    sandbox = handle(manager)
    sandbox._session.request = Mock(return_value=response(200, {  # pylint: disable=protected-access
        "status": "timed_out", "exit_code": None, "stdout": "o", "stderr": "", "stdout_truncated": True,
        "stderr_truncated": False, "duration": 2.0, "missing_executable": None}))
    result = sandbox.run_process(ProcessRequest(argv=("cat",), stdin=b"\x00-n\n", timeout=2, max_output_bytes=1))
    assert (result.status, result.exit_code, result.stdout, result.truncated) == (ProcessStatus.TIMED_OUT, None, "o", True)
    call = sandbox._session.request.call_args  # pylint: disable=protected-access
    assert call.args[:2] == ("POST", "http://sandbox:8001/sandboxes/handle-1/process")
    assert call.kwargs["json"] == {"argv": ["cat"], "shell": None, "stdin": base64.b64encode(b"\x00-n\n").decode(),
                                   "cwd": "/app", "timeout": 2, "max_output_bytes": 1}


@pytest.mark.parametrize("reply,expected", [
    (error(409, "SANDBOX_INVALIDATED"), SandboxInvalidatedError),
    (error(409, "SANDBOX_EXHAUSTED"), SandboxExhausted),
    (error(500, "SANDBOX_ERROR"), RemoteSandboxError),
    (error(410, "HANDLE_EXPIRED"), SandboxHandleGone),
    (error(404, "HANDLE_NOT_FOUND"), SandboxHandleNotFound),
])
def test_process_errors_are_distinct_exceptions(manager, reply, expected):
    sandbox = handle(manager)
    sandbox._session.request = Mock(return_value=reply)  # pylint: disable=protected-access
    with pytest.raises(expected):
        sandbox.run_process(ProcessRequest(argv=("id",)))


@pytest.mark.parametrize("reply,expected", [
    (error(404, "ARTIFACT_NOT_FOUND"), ArtifactNotFound),
    (error(404, "HANDLE_NOT_FOUND"), SandboxHandleNotFound),
    (error(410, "HANDLE_EXPIRED"), SandboxHandleGone),
    (error(410, "HANDLE_CLOSED"), SandboxHandleGone),
    (error(422, "ARTIFACT_INVALID"), ValueError),
    (error(500, "ARTIFACT_READ_FAILED"), ArtifactReadError),
    (error(500, "SANDBOX_ERROR"), RemoteSandboxError),
    (error(401, "UNAUTHORIZED"), RemoteSandboxError),
    (response(404, {"detail": "Not Found"}), RemoteSandboxError),  # e.g. wrong URL
])
def test_artifact_errors_are_distinct(manager, reply, expected):
    sandbox = handle(manager)
    sandbox._session.request = Mock(return_value=reply)  # pylint: disable=protected-access
    with pytest.raises(expected) as caught:
        sandbox.extract_file("/app/out.txt")
    is_missing_file = isinstance(caught.value, FileNotFoundError)
    assert is_missing_file == (expected is ArtifactNotFound)


def test_handle_errors_on_operations_are_runtime_errors(manager):
    sandbox = handle(manager)
    sandbox._session.request = Mock(return_value=error(404, "HANDLE_NOT_FOUND"))  # pylint: disable=protected-access
    with pytest.raises(SandboxHandleNotFound) as caught:
        sandbox.prepare_workdir({})
    assert isinstance(caught.value, RuntimeError)


def test_docker_session_closes_remote_handle_once_and_reports_quarantine(manager):
    manager._session.post = Mock(return_value=acquired())  # pylint: disable=protected-access
    manager._session.delete = Mock(return_value=response(200, {"status": "quarantined"}))  # pylint: disable=protected-access
    session = DockerSession(manager, Language.PYTHON)
    with pytest.raises(RuntimeError, match="quarantined"):
        session.close()
    session.close()
    assert manager._session.delete.call_count == 1  # pylint: disable=protected-access


def test_context_manager_disposes(manager):
    manager._session.post = Mock(return_value=acquired())  # pylint: disable=protected-access
    manager._session.delete = Mock(return_value=response(202, {"status": "closing"}))  # pylint: disable=protected-access
    with manager.acquire_sandbox(Language.PYTHON) as sandbox:
        pass
    assert sandbox.disposal_status is DisposalStatus.CLOSING
