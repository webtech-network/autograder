"""Unit tests for the grading service."""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch

from web.service.grading_service import (
    GradingRequest,
    _node_to_dict,
    _run_pipeline,
    grade_submission,
)
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus


@pytest.mark.asyncio
async def test_grade_submission_success():
    """Test successful grading of a submission."""
    # Mock dependencies
    mock_pipeline = Mock()
    mock_result = Mock()
    mock_result.final_score = 85.5
    mock_result.feedback = "Good work!"
    mock_result.result_tree = Mock()
    mock_result.result_tree.root = Mock()
    mock_result.result_tree.root.to_dict = Mock(return_value={"score": 85.5})
    mock_result.focus = Mock()
    mock_result.focus.to_dict = Mock(return_value={"areas": ["testing"]})

    from autograder.models.pipeline_execution import PipelineStatus as AutograderPipelineStatus
    mock_execution = Mock()
    mock_execution.result = mock_result
    mock_execution.start_time = time.time()
    mock_execution.status = AutograderPipelineStatus.SUCCESS
    mock_execution.step_results = []
    mock_execution.get_pipeline_execution_summary = Mock(return_value={
        "status": "success",
        "steps": ["pre_flight", "build_tree", "grade"]
    })
    mock_pipeline.run = Mock(return_value=mock_execution)

    with patch("web.service.grading_service.build_pipeline", return_value=mock_pipeline), \
         patch("web.service.grading_service.get_session") as mock_session, \
         patch("asyncio.to_thread", return_value=mock_execution):

        # Mock session and repositories
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_submission_repo = Mock()
        mock_result_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_submission_repo.update = AsyncMock()
        mock_result_repo.create = AsyncMock()
        mock_session_instance.commit = AsyncMock()

        with patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo):

            from web.service.grading_service import GradingRequest
            request = GradingRequest(
                submission_id=1,
                grading_config_id=1,
                template_name="input_output",
                criteria_config={"tests": []},
                setup_config={},
                feedback_config={},
                include_feedback=True,
                language="python",
                username="student1",
                external_user_id="user_001",
                submission_files={"main.py": {"filename": "main.py", "content": "print('hello')"}}
            )
            await grade_submission(request)

            # Verify status updates
            assert mock_submission_repo.update_status.call_count == 1
            mock_submission_repo.update_status.assert_called_with(1, SubmissionStatus.PROCESSING)

            # Verify result creation
            assert mock_result_repo.create.call_count == 1
            create_call = mock_result_repo.create.call_args[1]
            assert create_call["submission_id"] == 1
            assert create_call["final_score"] == 85.5
            assert create_call["pipeline_status"] == PipelineStatus.SUCCESS


@pytest.mark.asyncio
async def test_grade_submission_pipeline_failure():
    """Test grading when pipeline fails."""
    mock_pipeline = Mock()
    from autograder.models.pipeline_execution import PipelineStatus as AutograderPipelineStatus
    from autograder.models.dataclass.step_result import StepStatus, StepName
    
    mock_execution = Mock()
    mock_execution.result = None  # Pipeline failed
    mock_execution.start_time = time.time()
    mock_execution.status = AutograderPipelineStatus.FAILED
    
    mock_failed_step = Mock()
    mock_failed_step.status = StepStatus.FAIL
    mock_failed_step.step = StepName.PRE_FLIGHT
    mock_failed_step.error = "Syntax error"
    mock_failed_step.error_data = []
    
    mock_execution.step_results = [mock_failed_step]
    mock_execution.get_previous_step = Mock(return_value=mock_failed_step)
    mock_execution.get_pipeline_execution_summary = Mock(return_value={
        "status": "failed",
        "failed_at_step": "PreFlightStep"
    })

    mock_pipeline.run = Mock(return_value=mock_execution)

    with patch("web.service.grading_service.build_pipeline", return_value=mock_pipeline), \
         patch("web.service.grading_service.get_session") as mock_session, \
         patch("web.service.grading_service.generate_preflight_feedback", return_value="Fix syntax errors"), \
         patch("asyncio.to_thread", return_value=mock_execution):

        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_submission_repo = Mock()
        mock_result_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_result_repo.create = AsyncMock()
        mock_session_instance.commit = AsyncMock()

        with patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo):

            from web.service.grading_service import GradingRequest
            request = GradingRequest(
                submission_id=2,
                grading_config_id=1,
                template_name="input_output",
                criteria_config={"tests": []},
                setup_config={},
                feedback_config={},
                include_feedback=True,
                language="python",
                username="student2",
                external_user_id="user_002",
                submission_files={"main.py": {"filename": "main.py", "content": "invalid code"}}
            )
            await grade_submission(request)

            # Verify failure was recorded
            create_call = mock_result_repo.create.call_args[1]
            assert create_call["final_score"] == 0.0
            assert create_call["pipeline_status"] == PipelineStatus.FAILED
            assert create_call["failed_at_step"] == "PreFlightStep"


def test_node_to_dict():
    """Test node to dict conversion."""
    # Test with object that has to_dict method
    mock_node = Mock()
    mock_node.to_dict = Mock(return_value={"type": "node", "score": 100})

    result = _node_to_dict(mock_node)
    assert result == {"type": "node", "score": 100}

    # Test with None
    result = _node_to_dict(None)
    assert result == {}

    # Test with list
    mock_nodes = [
        Mock(to_dict=Mock(return_value={"id": 1})),
        Mock(to_dict=Mock(return_value={"id": 2}))
    ]
    result = _node_to_dict(mock_nodes)
    assert result == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_run_pipeline_hydrates_evaluation_context():
    """Stored API data is reconstructed as typed core evaluation context."""
    mock_pipeline = Mock()
    mock_pipeline.run.return_value = Mock()
    request = GradingRequest(
        submission_id=3,
        grading_config_id=5,
        template_name="static_analysis",
        criteria_config={"base": {}},
        setup_config={},
        feedback_config={},
        include_feedback=False,
        language="python",
        username="student",
        external_user_id="user-003",
        submission_files={
            "main.py": {
                "filename": "main.py",
                "content": "print('hello')",
                "changed_lines": [1, 3],
                "file_metadata": {"change_status": "modified"},
            }
        },
        evaluation_scope={"scoped_files": ["main.py"]},
    )

    with patch(
        "web.service.grading_service.build_pipeline",
        return_value=mock_pipeline,
    ):
        result = await _run_pipeline(request)

    assert result is mock_pipeline.run.return_value
    core_submission = mock_pipeline.run.call_args.args[0]
    assert core_submission.evaluation_scope.scoped_files == ["main.py"]
    assert core_submission.submission_files["main.py"].changed_lines == {1, 3}
    assert core_submission.submission_files["main.py"].metadata == {
        "change_status": "modified",
    }
