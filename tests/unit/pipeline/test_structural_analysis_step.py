import pytest
from unittest.mock import MagicMock, patch
from autograder.steps.structural_analysis_step import StructuralAnalysisStep
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.dataclass.step_result import StepName, StepStatus
from sandbox_manager.models.sandbox_models import Language

@pytest.fixture
def mock_pipeline_exec():
    submission = Submission(
        username="testuser",
        user_id=1,
        assignment_id=1,
        submission_files={
            "main.py": SubmissionFile(filename="main.py", content="print('hello')"),
            "data.txt": SubmissionFile(filename="data.txt", content="some data")
        },
        language=Language.PYTHON
    )
    pipeline_exec = PipelineExecution.start_execution(submission)
    return pipeline_exec

def test_structural_analysis_step_name():
    step = StructuralAnalysisStep()
    assert step.step_name == StepName.STRUCTURAL_ANALYSIS

@patch("autograder.steps.structural_analysis_step.SgRoot")
def test_structural_analysis_step_execution_success(mock_sg_root, mock_pipeline_exec):
    # Setup mock
    mock_root_instance = MagicMock()
    mock_sg_root.return_value = mock_root_instance
    
    step = StructuralAnalysisStep()
    result_exec = step.execute(mock_pipeline_exec)
    
    # Verify StepResult
    step_result = result_exec.get_step_result(StepName.STRUCTURAL_ANALYSIS)
    assert step_result.status == StepStatus.SUCCESS
    assert "main.py" in step_result.data.roots
    assert "data.txt" not in step_result.data.roots # Heuristic should skip .txt
    assert step_result.data.roots["main.py"] == mock_root_instance
    
    # Verify SgRoot called correctly
    mock_sg_root.assert_called_once_with("print('hello')", "python")

@patch("autograder.steps.structural_analysis_step.SgRoot")
def test_structural_analysis_step_parsing_failure(mock_sg_root, mock_pipeline_exec):
    # Setup mock to raise error for parsing
    mock_sg_root.side_effect = Exception("Parsing failed")
    
    step = StructuralAnalysisStep()
    result_exec = step.execute(mock_pipeline_exec)
    
    # Verify StepResult is still SUCCESS (graceful handling)
    step_result = result_exec.get_step_result(StepName.STRUCTURAL_ANALYSIS)
    assert step_result.status == StepStatus.SUCCESS
    assert "main.py" in step_result.data.roots
    assert step_result.data.roots["main.py"] is None # Failed parsing results in None

def test_structural_analysis_step_no_language(mock_pipeline_exec):
    mock_pipeline_exec.submission.language = None
    step = StructuralAnalysisStep()
    result_exec = step.execute(mock_pipeline_exec)
    
    step_result = result_exec.get_step_result(StepName.STRUCTURAL_ANALYSIS)
    assert step_result.status == StepStatus.SUCCESS
    assert step_result.data.roots == {}
