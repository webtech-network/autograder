import pytest
from unittest.mock import MagicMock, patch
from autograder.services.sandbox_service import SandboxService
from autograder.models.dataclass.submission import Submission
from sandbox_manager.models.sandbox_models import Language, ResponseCategory

@pytest.fixture
def sandbox_service():
    """Fixture for SandboxService."""
    return SandboxService()

@pytest.fixture
def mock_sandbox_manager():
    """Fixture for mocked sandbox manager."""
    with patch("sandbox_manager.manager.get_sandbox_manager") as mock_get:
        manager_mock = MagicMock()
        mock_get.return_value = manager_mock
        yield manager_mock

def test_create_sandbox_no_language(sandbox_service):
    """Test creating sandbox without language."""
    submission = Submission(username="test", user_id="1", assignment_id="1", language=None, submission_files={"main.py": "..."})
    with pytest.raises(ValueError, match="Submission language is required"):
        sandbox_service.create_sandbox(submission)

def test_create_sandbox_manager_exception(sandbox_service, mock_sandbox_manager):
    """Test manager exception during sandbox creation."""
    submission = Submission(username="test", user_id="1", assignment_id="1", language=Language.PYTHON, submission_files={"main.py": "..."})
    mock_sandbox_manager.get_sandbox.side_effect = Exception("Pool error")
    
    result = sandbox_service.create_sandbox(submission)
    assert result is None

def test_create_sandbox_workdir_failure_releases_container(sandbox_service, mock_sandbox_manager):
    """Test releasing container if workdir preparation fails."""
    submission = Submission(username="test", user_id="1", assignment_id="1", language=Language.PYTHON, submission_files={"main.py": "..."})
    mock_sandbox = MagicMock()
    mock_sandbox.prepare_workdir.side_effect = IOError("Disk full")
    mock_sandbox_manager.get_sandbox.return_value = mock_sandbox
    
    result = sandbox_service.create_sandbox(submission)
    
    assert result is None
    # CRITICAL: Verify the container was not leaked
    mock_sandbox_manager.release_sandbox.assert_called_once_with(Language.PYTHON, mock_sandbox)

def test_create_sandbox_success(sandbox_service, mock_sandbox_manager):
    """Test successful sandbox creation."""
    submission = Submission(username="test", user_id="1", assignment_id="1", language=Language.PYTHON, submission_files={"main.py": "..."})
    mock_sandbox = MagicMock()
    mock_sandbox_manager.get_sandbox.return_value = mock_sandbox
    
    result = sandbox_service.create_sandbox(submission)
    assert result == mock_sandbox
    mock_sandbox.prepare_workdir.assert_called_once_with(submission.submission_files)

def test_create_sandbox_success_no_files(sandbox_service, mock_sandbox_manager):
    """Test sandbox creation with no files."""
    submission = Submission(username="test", user_id="1", assignment_id="1", language=Language.PYTHON, submission_files=None)
    mock_sandbox = MagicMock()
    mock_sandbox_manager.get_sandbox.return_value = mock_sandbox
    
    result = sandbox_service.create_sandbox(submission)
    assert result == mock_sandbox
    mock_sandbox.prepare_workdir.assert_not_called()

def test_release_sandbox_success(sandbox_service, mock_sandbox_manager):
    """Test successful sandbox release."""
    mock_sandbox = MagicMock()
    sandbox_service.release_sandbox(Language.PYTHON, mock_sandbox)
    mock_sandbox_manager.release_sandbox.assert_called_once_with(Language.PYTHON, mock_sandbox)

def test_release_sandbox_exception_handled(sandbox_service, mock_sandbox_manager):
    """Test exception handling during sandbox release."""
    mock_sandbox = MagicMock()
    mock_sandbox_manager.release_sandbox.side_effect = Exception("Cannot release")
    # Should not raise
    sandbox_service.release_sandbox(Language.PYTHON, mock_sandbox)

def test_run_setup_command_no_sandbox(sandbox_service):
    """Test running setup command without sandbox."""
    response = sandbox_service.run_setup_command(None, "echo hi")
    assert response.category == ResponseCategory.SYSTEM_ERROR
    assert "Sandbox environment is required" in response.stderr

def test_run_setup_command_dict_missing_command(sandbox_service):
    """Test running setup command with missing command in dict."""
    mock_sandbox = MagicMock()
    response = sandbox_service.run_setup_command(mock_sandbox, {"name": "Install deps"})
    assert response.category == ResponseCategory.SYSTEM_ERROR
    # Expect error about missing field
    assert response.exit_code == -1

def test_run_setup_command_dict_success(sandbox_service):
    """Test successful setup command execution from dict."""
    mock_sandbox = MagicMock()
    expected_response = MagicMock(category=ResponseCategory.SUCCESS)
    mock_sandbox.run_command.return_value = expected_response
    
    response = sandbox_service.run_setup_command(mock_sandbox, {"name": "Install deps", "command": "pip install -r req.txt"})
    assert response == expected_response
    mock_sandbox.run_command.assert_called_once_with("pip install -r req.txt")

def test_run_setup_command_invalid_format(sandbox_service):
    """Test setup command with invalid format."""
    mock_sandbox = MagicMock()
    response = sandbox_service.run_setup_command(mock_sandbox, 12345)
    assert response.category == ResponseCategory.SYSTEM_ERROR

def test_run_setup_command_execution_exception(sandbox_service):
    """Test setup command execution exception."""
    mock_sandbox = MagicMock()
    mock_sandbox.run_command.side_effect = Exception("Command crashed")
    
    response = sandbox_service.run_setup_command(mock_sandbox, "echo hi")
    assert response.category == ResponseCategory.SYSTEM_ERROR
    assert "Command crashed" in response.stderr
