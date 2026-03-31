import pytest
from unittest.mock import MagicMock, patch
from autograder.autograder import AutograderPipeline
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language

@pytest.fixture
def submission():
    """Fixture providing a mock submission for testing."""
    return Submission(
        username="testuser",
        user_id=1,
        assignment_id=1,
        language=Language.PYTHON,
        submission_files={"main.py": SubmissionFile(filename="main.py", content="print('hello')")}
    )

@pytest.fixture
def pipeline_exec(submission):
    """Fixture providing a PipelineExecution instance starting from submission."""
    return PipelineExecution.start_execution(submission)

@patch("sandbox_manager.manager.get_sandbox_manager")
def test_cleanup_sandbox_called_after_pipeline_run(mock_get_manager, pipeline_exec):
    """Verifies that _cleanup_sandbox is called and releases the sandbox correctly."""
    mock_manager = mock_get_manager.return_value
    mock_sandbox = MagicMock(spec=SandboxContainer)
    
    # Manually attach sandbox to execution (simulating SandboxStep execution)
    pipeline_exec.sandbox = mock_sandbox
    
    pipeline = AutograderPipeline()
    # Mock steps to do nothing
    pipeline.run = MagicMock(return_value=pipeline_exec)
    
    # We want to test the _cleanup_sandbox method directly or via a real run
    # Let's test _cleanup_sandbox directly to verify it uses the property
    pipeline._cleanup_sandbox(pipeline_exec)
    
    mock_manager.release_sandbox.assert_called_once_with(Language.PYTHON, mock_sandbox)

@patch("sandbox_manager.manager.get_sandbox_manager")
def test_cleanup_sandbox_even_on_step_failure(mock_get_manager, pipeline_exec):
    """Ensures that sandbox cleanup occurs even if the pipeline status is FAILED."""
    mock_manager = mock_get_manager.return_value
    mock_sandbox = MagicMock(spec=SandboxContainer)
    
    # Simulate a failed execution that still has a sandbox
    pipeline_exec.sandbox = mock_sandbox
    pipeline_exec.status = PipelineStatus.FAILED
    
    pipeline = AutograderPipeline()
    pipeline._cleanup_sandbox(pipeline_exec)
    
    # Cleanup should still happen
    mock_manager.release_sandbox.assert_called_once_with(Language.PYTHON, mock_sandbox)

@patch("sandbox_manager.manager.get_sandbox_manager")
def test_cleanup_no_sandbox_no_call(mock_get_manager, pipeline_exec):
    """Verifies that no sandbox release call is made if no sandbox is attached."""
    mock_manager = mock_get_manager.return_value
    
    pipeline_exec.sandbox = None
    
    pipeline = AutograderPipeline()
    pipeline._cleanup_sandbox(pipeline_exec)
    
    mock_manager.release_sandbox.assert_not_called()
