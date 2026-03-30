import pytest
from unittest.mock import MagicMock, patch
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepName, StepStatus
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.steps.sandbox_step import SandboxStep
from sandbox_manager.sandbox_container import SandboxContainer

@pytest.fixture
def submission():
    """Fixture providing a mock submission for testing."""
    return Submission(
        username="testuser",
        user_id=1,
        assignment_id=1,
        submission_files={"main.py": SubmissionFile(filename="main.py", content="print('hello')")}
    )

@pytest.fixture
def pipeline_exec(submission):
    """Fixture providing a PipelineExecution instance starting from submission."""
    return PipelineExecution.start_execution(submission)

@patch("autograder.steps.sandbox_step.PreFlightService")
def test_sandbox_step_success(mock_services_class, pipeline_exec):
    """Tests successful sandbox creation and setup command execution."""
    # Setup mock template
    mock_template = MagicMock()
    mock_template.requires_sandbox = True
    pipeline_exec.add_step_result(MagicMock(step=StepName.LOAD_TEMPLATE, data=mock_template))
    
    # Setup mock service and sandbox
    mock_service = mock_services_class.return_value
    mock_sandbox = MagicMock(spec=SandboxContainer)
    mock_service.create_sandbox.return_value = mock_sandbox
    mock_service.setup_commands = ["echo 'hello'"]
    mock_service.check_setup_commands.return_value = True
    
    step = SandboxStep(setup_config={})
    result_exec = step.execute(pipeline_exec)
    
    # Assertions
    assert result_exec.sandbox is mock_sandbox
    assert result_exec.get_sandbox() is mock_sandbox
    step_result = result_exec.get_step_result(StepName.SANDBOX)
    assert step_result.status == StepStatus.SUCCESS
    assert step_result.data is mock_sandbox

@patch("autograder.steps.sandbox_step.PreFlightService")
def test_sandbox_step_skipped_when_not_required(mock_services_class, pipeline_exec):
    """Tests that sandbox step is skipped if the template does not require it."""
    # Setup mock template
    mock_template = MagicMock()
    mock_template.requires_sandbox = False
    pipeline_exec.add_step_result(MagicMock(step=StepName.LOAD_TEMPLATE, data=mock_template))
    
    step = SandboxStep(setup_config={})
    result_exec = step.execute(pipeline_exec)
    
    # Assertions
    assert result_exec.sandbox is None
    step_result = result_exec.get_step_result(StepName.SANDBOX)
    assert step_result.status == StepStatus.SUCCESS
    assert step_result.data is None
    mock_services_class.return_value.create_sandbox.assert_not_called()

@patch("autograder.steps.sandbox_step.PreFlightService")
def test_sandbox_step_fails_on_setup_but_preserves_sandbox(mock_services_class, pipeline_exec):
    """Tests that sandbox is preserved for cleanup even if setup commands fail."""
    # Setup mock template
    mock_template = MagicMock()
    mock_template.requires_sandbox = True
    pipeline_exec.add_step_result(MagicMock(step=StepName.LOAD_TEMPLATE, data=mock_template))
    
    # Setup mock service and sandbox
    mock_service = mock_services_class.return_value
    mock_sandbox = MagicMock(spec=SandboxContainer)
    mock_service.create_sandbox.return_value = mock_sandbox
    mock_service.setup_commands = ["fail_command"]
    mock_service.check_setup_commands.return_value = False
    mock_service.has_errors.return_value = True
    mock_service.get_error_messages.return_value = ["Setup failed"]
    
    step = SandboxStep(setup_config={})
    result_exec = step.execute(pipeline_exec)
    
    # Assertions
    assert result_exec.sandbox is mock_sandbox  # CRITICAL: Sandbox must be preserved for cleanup
    step_result = result_exec.get_step_result(StepName.SANDBOX)
    assert step_result.status == StepStatus.FAIL
    assert "Setup failed" in step_result.error
