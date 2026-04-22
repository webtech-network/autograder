"""Unit tests for the deliberate execution service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from web.service.deliberate_execution_service import execute_code, _get_error_message
from web.schemas.execution import DeliberateCodeExecutionRequest, DeliberateCodeExecutionResponse
from sandbox_manager.models.sandbox_models import ResponseCategory, CommandResponse


def _make_request(language="python", files=None, command="python main.py", test_cases=None):
    """Helper to build a DeliberateCodeExecutionRequest."""
    if files is None:
        files = [{"filename": "main.py", "content": "print('hello')"}]
    return DeliberateCodeExecutionRequest(
        language=language,
        submission_files=files,
        program_command=command,
        test_cases=test_cases,
    )


def _make_command_response(stdout="hello\n", stderr="", exit_code=0,
                           execution_time=0.1, category=ResponseCategory.SUCCESS):
    return CommandResponse(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        execution_time=execution_time,
        category=category,
    )


# ---------------------------------------------------------------------------
# _get_error_message tests
# ---------------------------------------------------------------------------

def test_get_error_message_success_returns_none():
    result = _make_command_response(category=ResponseCategory.SUCCESS)
    assert _get_error_message(result) is None


def test_get_error_message_compilation_error():
    result = _make_command_response(
        stderr="undefined symbol", category=ResponseCategory.COMPILATION_ERROR
    )
    msg = _get_error_message(result)
    assert "Compilation failed" in msg
    assert "undefined symbol" in msg


def test_get_error_message_runtime_error_no_stderr():
    result = _make_command_response(stderr="", category=ResponseCategory.RUNTIME_ERROR)
    msg = _get_error_message(result)
    assert msg == "Runtime error occurred"


def test_get_error_message_timeout():
    result = _make_command_response(stderr="", category=ResponseCategory.TIMEOUT)
    assert _get_error_message(result) == "Execution timed out"


def test_get_error_message_system_error_with_stderr():
    result = _make_command_response(
        stderr="OOM killed", category=ResponseCategory.SYSTEM_ERROR
    )
    msg = _get_error_message(result)
    assert "System error occurred" in msg
    assert "OOM killed" in msg


# ---------------------------------------------------------------------------
# execute_code – unsupported language
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_unsupported_language():
    """execute_code raises ValueError for an unknown language.

    The schema validates the language too, so we use a valid language in the
    request but patch the Language enum inside the service to simulate a lookup
    failure (e.g., the enum is ahead of the schema in a future change).
    """
    request = _make_request(language="python")
    mock_language = Mock()
    mock_language.__getitem__ = Mock(side_effect=KeyError("unknown"))

    with patch("web.service.deliberate_execution_service.Language", mock_language):
        with pytest.raises(ValueError, match="Unsupported language"):
            await execute_code(request)


# ---------------------------------------------------------------------------
# execute_code – sandbox unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_sandbox_unavailable():
    """execute_code raises ValueError when sandbox manager is not initialized."""
    request = _make_request()
    with patch(
        "web.service.deliberate_execution_service.get_sandbox_manager",
        side_effect=ValueError("SandboxManager has not been initialized"),
    ):
        with pytest.raises(ValueError, match="Sandbox manager not available"):
            await execute_code(request)


# ---------------------------------------------------------------------------
# execute_code – successful execution (no inputs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_success_no_inputs():
    """execute_code returns a successful response when there are no inputs."""
    cmd_response = _make_command_response(stdout="hello\n")

    mock_sandbox = Mock()
    mock_sandbox.prepare_workdir = Mock()
    mock_sandbox.run_command = Mock(return_value=cmd_response)

    mock_manager = Mock()
    mock_manager.get_sandbox = Mock(return_value=mock_sandbox)
    mock_manager.release_sandbox = Mock()

    request = _make_request(test_cases=None)

    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=mock_manager), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=cmd_response)):

        response = await execute_code(request)

    assert isinstance(response, DeliberateCodeExecutionResponse)
    assert len(response.results) == 1
    assert response.results[0].category == ResponseCategory.SUCCESS
    assert response.results[0].output == "hello\n"
    assert response.results[0].error_message is None
    mock_manager.release_sandbox.assert_called_once()


# ---------------------------------------------------------------------------
# execute_code – successful execution (with inputs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_success_with_inputs():
    """execute_code returns a successful response when inputs are provided."""
    cmd_response = _make_command_response(stdout="42\n")

    mock_sandbox = Mock()
    mock_sandbox.prepare_workdir = Mock()
    mock_sandbox.run_commands = Mock(return_value=cmd_response)

    mock_manager = Mock()
    mock_manager.get_sandbox = Mock(return_value=mock_sandbox)
    mock_manager.release_sandbox = Mock()

    request = _make_request(test_cases=[["5", "7"]])

    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=mock_manager), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=cmd_response)):

        response = await execute_code(request)

    assert len(response.results) == 1
    assert response.results[0].category == ResponseCategory.SUCCESS
    assert response.results[0].output == "42\n"
    mock_manager.release_sandbox.assert_called_once()


# ---------------------------------------------------------------------------
# execute_code – execution error (exception inside sandbox block)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_execution_error():
    """execute_code returns a SYSTEM_ERROR response when an exception is raised."""
    mock_sandbox = Mock()
    mock_sandbox.prepare_workdir = Mock()

    mock_manager = Mock()
    mock_manager.get_sandbox = Mock(return_value=mock_sandbox)
    mock_manager.release_sandbox = Mock()

    request = _make_request()

    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=mock_manager), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("container crashed"))):

        response = await execute_code(request)

    assert len(response.results) == 1
    assert response.results[0].category == ResponseCategory.SYSTEM_ERROR
    assert response.results[0].error_message == "An unexpected error occurred. Please try again later."
    assert "container crashed" not in response.results[0].error_message
    assert response.results[0].output == ""
    # Sandbox must still be released in the finally block
    mock_manager.release_sandbox.assert_called_once()


# ---------------------------------------------------------------------------
# execute_code – execution error with multiple test cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_execution_error_multiple_test_cases():
    """On exception, SYSTEM_ERROR count matches the number of requested test cases."""
    mock_sandbox = Mock()
    mock_sandbox.prepare_workdir = Mock()

    mock_manager = Mock()
    mock_manager.get_sandbox = Mock(return_value=mock_sandbox)
    mock_manager.release_sandbox = Mock()

    request = _make_request(test_cases=[["1"], ["2"], ["3"]])

    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=mock_manager), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("container crashed"))):

        response = await execute_code(request)

    assert len(response.results) == 3
    for result in response.results:
        assert result.category == ResponseCategory.SYSTEM_ERROR
        assert result.error_message == "An unexpected error occurred. Please try again later."
        assert result.output == ""
    mock_manager.release_sandbox.assert_called_once()


# ---------------------------------------------------------------------------
# execute_code – runtime error response from sandbox
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_code_runtime_error_response():
    """execute_code surfaces RUNTIME_ERROR category from sandbox response."""
    cmd_response = _make_command_response(
        stdout="",
        stderr="ZeroDivisionError: division by zero",
        exit_code=1,
        category=ResponseCategory.RUNTIME_ERROR,
    )

    mock_sandbox = Mock()
    mock_sandbox.prepare_workdir = Mock()

    mock_manager = Mock()
    mock_manager.get_sandbox = Mock(return_value=mock_sandbox)
    mock_manager.release_sandbox = Mock()

    request = _make_request()

    with patch("web.service.deliberate_execution_service.get_sandbox_manager", return_value=mock_manager), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=cmd_response)):

        response = await execute_code(request)

    assert len(response.results) == 1
    assert response.results[0].category == ResponseCategory.RUNTIME_ERROR
    assert "Runtime error occurred" in response.results[0].error_message
    assert "ZeroDivisionError" in response.results[0].error_message
