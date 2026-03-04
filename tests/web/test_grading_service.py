"""Unit tests for the grading service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from web.service.grading_service import grade_submission, _node_to_dict
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

    mock_execution = Mock()
    mock_execution.result = mock_result
    mock_execution.get_pipeline_execution_summary = Mock(return_value={
        "status": "success",
        "steps": ["pre_flight", "build_tree", "grade"]
    })

    mock_pipeline.run = Mock(return_value=mock_execution)

    with patch("web.services.grading_service.build_pipeline", return_value=mock_pipeline), \
         patch("web.services.grading_service.get_session") as mock_session, \
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

        with patch("web.services.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.services.grading_service.ResultRepository", return_value=mock_result_repo):

            await grade_submission(
                submission_id=1,
                grading_config_id=1,
                template_name="input_output",
                criteria_config={"tests": []},
                setup_config={},
                language="python",
                username="student1",
                external_user_id="user_001",
                submission_files={"main.py": {"filename": "main.py", "content": "print('hello')"}}
            )

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
    mock_execution = Mock()
    mock_execution.result = None  # Pipeline failed
    mock_execution.step_results = [Mock()]
    mock_execution.get_previous_step = Mock(return_value=Mock(error="Syntax error"))
    mock_execution.get_pipeline_execution_summary = Mock(return_value={
        "status": "failed",
        "failed_at_step": "PreFlightStep"
    })

    mock_pipeline.run = Mock(return_value=mock_execution)

    with patch("web.services.grading_service.build_pipeline", return_value=mock_pipeline), \
         patch("web.services.grading_service.get_session") as mock_session, \
         patch("web.services.grading_service.generate_preflight_feedback", return_value="Fix syntax errors"), \
         patch("asyncio.to_thread", return_value=mock_execution):

        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_submission_repo = Mock()
        mock_result_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_result_repo.create = AsyncMock()
        mock_session_instance.commit = AsyncMock()

        with patch("web.services.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.services.grading_service.ResultRepository", return_value=mock_result_repo):

            await grade_submission(
                submission_id=2,
                grading_config_id=1,
                template_name="input_output",
                criteria_config={"tests": []},
                setup_config={},
                language="python",
                username="student2",
                external_user_id="user_002",
                submission_files={"main.py": {"filename": "main.py", "content": "invalid code"}}
            )

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

