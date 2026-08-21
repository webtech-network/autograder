"""
Integration tests for contribution-aware evaluation features.

Tests cover:
1. EvaluationScope propagation through the pipeline
2. changed_lines propagation through the pipeline
3. file_metadata passthrough to test functions
4. GradingService hydration of contribution-aware fields from HTTP payload format

These tests use the static_analysis template (no sandbox) so they can run
without Docker infrastructure.
"""

import time

import pytest
from unittest.mock import AsyncMock, Mock, patch

from autograder.autograder import build_pipeline
from autograder.models.abstract.test_function import TestFunction
from autograder.models.criteria_tree import CategoryNode, CriteriaTree, TestNode
from autograder.models.dataclass.submission import (
    EvaluationScope,
    Submission,
    SubmissionFile,
)
from autograder.models.dataclass.test_result import TestResult
from autograder.services.grader.grader_service import GraderService
from web.service.grading_service import GradingRequest, grade_submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_submission(
    files: dict[str, SubmissionFile],
    evaluation_scope: EvaluationScope | None = None,
) -> Submission:
    """Build a Submission with optional contribution-aware fields."""
    return Submission(
        username="integration-student",
        user_id="integration-user",
        assignment_id=1,
        submission_files=files,
        language=None,  # static_analysis doesn't require language
        locale="en",
        evaluation_scope=evaluation_scope,
    )


def _static_analysis_criteria(forbidden_imports: list) -> dict:
    """Build a criteria config for static_analysis with forbidden imports."""
    return {
        "base": {
            "weight": 100.0,
            "tests": [
                {
                    "name": f"no_{imp}",
                    "type": "forbidden_import",
                    "forbidden_imports": [imp],
                    "submission_language": "python",
                }
                for imp in forbidden_imports
            ],
        }
    }


class ContextCapturingTest(TestFunction):
    """Test function that captures files, evaluation_scope, and file_metadata."""

    def __init__(self):
        self.files = None
        self.kwargs = None

    @property
    def name(self) -> str:
        return "context_capture"

    @property
    def description(self) -> str:
        return "Capture contribution-aware context."

    @property
    def parameter_description(self) -> list:
        return []

    def execute(self, files, sandbox, *args, **kwargs) -> TestResult:
        self.files = files
        self.kwargs = kwargs
        return TestResult(
            test_name=self.name,
            score=100.0,
            report="Context captured.",
        )


# ---------------------------------------------------------------------------
# Integration: EvaluationScope through the pipeline
# ---------------------------------------------------------------------------


class TestEvaluationScopeIntegration:
    """Verify evaluation_scope restricts structural analysis and propagates to test functions."""

    def test_structural_analysis_respects_evaluation_scope(self):
        """Pipeline with 2 files but scope limited to 1 → structural analysis parses only scoped file."""
        from sandbox_manager.models.sandbox_models import Language

        criteria = _static_analysis_criteria(["os"])

        files = {
            "main.py": SubmissionFile(filename="main.py", content="import os\nx = 1"),
            "helper.py": SubmissionFile(filename="helper.py", content="import os\ny = 2"),
        }
        scope = EvaluationScope(scoped_files=["main.py"])

        submission = Submission(
            username="scope-student",
            user_id="scope-user",
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON,
            locale="en",
            evaluation_scope=scope,
        )

        pipeline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        execution = pipeline.run(submission)

        # Pipeline should succeed
        assert execution.result is not None

        # Structural analysis should have only parsed main.py (the scoped file)
        sa_result = execution.get_structural_analysis_result()
        assert sa_result is not None
        assert sa_result.available is True
        assert "main.py" in sa_result.roots
        assert "helper.py" not in sa_result.roots

    def test_grading_with_evaluation_scope_passes_to_test_functions(self):
        """Verify evaluation_scope is propagated as kwarg to test functions via GraderService."""
        capturing_test = ContextCapturingTest()
        criteria_tree = CriteriaTree(
            base=CategoryNode(
                name="base",
                weight=100,
                tests=[
                    TestNode(
                        name="context_capture",
                        test_function=capturing_test,
                        file_target=["main.py"],
                    )
                ],
            )
        )

        files = {
            "main.py": SubmissionFile(filename="main.py", content="x = 1"),
        }
        scope = EvaluationScope(scoped_files=["main.py"])

        GraderService().grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=files,
            evaluation_scope=scope,
        )

        assert capturing_test.kwargs is not None
        assert capturing_test.kwargs["evaluation_scope"] is scope

    def test_grading_without_evaluation_scope_processes_all_files(self):
        """Without scope, all submission files are processed normally."""
        from sandbox_manager.models.sandbox_models import Language

        criteria = _static_analysis_criteria(["os"])
        files = {
            "main.py": SubmissionFile(filename="main.py", content="x = 1"),
            "helper.py": SubmissionFile(filename="helper.py", content="y = 2"),
        }

        submission = Submission(
            username="noscope-student",
            user_id="noscope-user",
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON,
            locale="en",
            evaluation_scope=None,
        )

        pipeline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        execution = pipeline.run(submission)

        assert execution.result is not None

        # Without scope, structural analysis should parse both files
        sa_result = execution.get_structural_analysis_result()
        assert sa_result is not None
        assert "main.py" in sa_result.roots
        assert "helper.py" in sa_result.roots

    def test_evaluation_scope_none_passed_to_test_functions(self):
        """When evaluation_scope is None, test functions receive None."""
        capturing_test = ContextCapturingTest()
        criteria_tree = CriteriaTree(
            base=CategoryNode(
                name="base",
                weight=100,
                tests=[
                    TestNode(
                        name="context_capture",
                        test_function=capturing_test,
                    )
                ],
            )
        )

        files = {"main.py": SubmissionFile(filename="main.py", content="x = 1")}

        GraderService().grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=files,
            evaluation_scope=None,
        )

        assert capturing_test.kwargs["evaluation_scope"] is None


# ---------------------------------------------------------------------------
# Integration: changed_lines through the pipeline
# ---------------------------------------------------------------------------


class TestChangedLinesIntegration:
    """Verify changed_lines propagation through the pipeline."""

    def test_changed_lines_propagated_through_pipeline(self):
        """SubmissionFile with changed_lines → structural analysis captures them."""
        from sandbox_manager.models.sandbox_models import Language

        criteria = _static_analysis_criteria(["os"])
        files = {
            "main.py": SubmissionFile(
                filename="main.py",
                content="import os\nx = 1",
                changed_lines={1, 2},
            ),
        }

        submission = Submission(
            username="cl-student",
            user_id="cl-user",
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON,
            locale="en",
        )

        pipeline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        execution = pipeline.run(submission)

        assert execution.result is not None

        # Structural analysis should carry the changed_lines
        sa_result = execution.get_structural_analysis_result()
        assert sa_result is not None
        assert "main.py" in sa_result.changed_lines
        assert sa_result.changed_lines["main.py"] == {1, 2}

    def test_no_changed_lines_still_works(self):
        """Submission without changed_lines → pipeline works normally, is_contribution_aware=False."""
        from sandbox_manager.models.sandbox_models import Language

        criteria = _static_analysis_criteria(["os"])
        file_obj = SubmissionFile(filename="main.py", content="x = 1")
        assert file_obj.is_contribution_aware is False

        files = {"main.py": file_obj}

        submission = Submission(
            username="no-cl-student",
            user_id="no-cl-user",
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON,
            locale="en",
        )

        pipeline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        execution = pipeline.run(submission)

        assert execution.result is not None
        assert execution.result.final_score == 100.0

        # Structural analysis should have empty changed_lines
        sa_result = execution.get_structural_analysis_result()
        assert sa_result.changed_lines == {}

    def test_changed_lines_set_means_contribution_aware(self):
        """SubmissionFile with changed_lines set → is_contribution_aware is True."""
        file_obj = SubmissionFile(
            filename="main.py",
            content="x = 1",
            changed_lines={1},
        )
        assert file_obj.is_contribution_aware is True


# ---------------------------------------------------------------------------
# Integration: file_metadata passthrough
# ---------------------------------------------------------------------------


class TestFileMetadataIntegration:
    """Verify file_metadata is available in test functions via file_metadata kwarg."""

    def test_file_metadata_available_in_test_function(self):
        """Test function receives file_metadata dict keyed by filename."""
        capturing_test = ContextCapturingTest()
        criteria_tree = CriteriaTree(
            base=CategoryNode(
                name="base",
                weight=100,
                tests=[
                    TestNode(
                        name="context_capture",
                        test_function=capturing_test,
                        file_target=["main.py"],
                    )
                ],
            )
        )

        metadata = {"change_status": "modified", "provider": "github"}
        files = {
            "main.py": SubmissionFile(
                filename="main.py",
                content="x = 1",
                metadata=metadata,
            ),
        }

        GraderService().grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=files,
        )

        assert capturing_test.kwargs is not None
        assert capturing_test.kwargs["file_metadata"] == {"main.py": metadata}
        assert capturing_test.kwargs["file_metadata"]["main.py"] is metadata

    def test_file_metadata_none_when_not_provided(self):
        """Test function receives file_metadata with None values when metadata is absent."""
        capturing_test = ContextCapturingTest()
        criteria_tree = CriteriaTree(
            base=CategoryNode(
                name="base",
                weight=100,
                tests=[
                    TestNode(
                        name="context_capture",
                        test_function=capturing_test,
                        file_target=["main.py"],
                    )
                ],
            )
        )

        files = {
            "main.py": SubmissionFile(filename="main.py", content="x = 1"),
        }

        GraderService().grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=files,
        )

        assert capturing_test.kwargs["file_metadata"] == {"main.py": None}

    def test_file_metadata_multi_file_only_targeted_files(self):
        """file_metadata contains only the files targeted by file_target."""
        capturing_test = ContextCapturingTest()
        criteria_tree = CriteriaTree(
            base=CategoryNode(
                name="base",
                weight=100,
                tests=[
                    TestNode(
                        name="context_capture",
                        test_function=capturing_test,
                        file_target=["main.py"],
                    )
                ],
            )
        )

        files = {
            "main.py": SubmissionFile(
                filename="main.py",
                content="x = 1",
                metadata={"change_status": "modified"},
            ),
            "helper.py": SubmissionFile(
                filename="helper.py",
                content="y = 2",
                metadata={"change_status": "added"},
            ),
        }

        GraderService().grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=files,
        )

        # Only main.py should be in file_metadata (file_target = ["main.py"])
        assert "main.py" in capturing_test.kwargs["file_metadata"]
        assert "helper.py" not in capturing_test.kwargs["file_metadata"]


# ---------------------------------------------------------------------------
# Integration: GradingService hydration of contribution-aware fields
# ---------------------------------------------------------------------------


class TestGradingServiceContributionAware:
    """Verify the grading service correctly hydrates contribution-aware fields."""

    @pytest.mark.asyncio
    async def test_grading_service_hydrates_evaluation_scope(self):
        """GradingRequest with evaluation_scope dict → AutograderSubmission has EvaluationScope object."""
        mock_result = Mock()
        mock_result.final_score = 100.0
        mock_result.feedback = None
        mock_result.result_tree = None
        mock_result.focus = Mock()
        mock_result.focus.to_dict = Mock(return_value={"base": []})
        mock_result.comparison = None

        mock_execution = Mock()
        mock_execution.result = mock_result
        mock_execution.start_time = time.time()
        mock_execution.step_results = []

        mock_submission_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_submission_repo.update = AsyncMock()

        mock_result_repo = Mock()
        mock_result_repo.create = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        captured_submission = {}

        def capture_pipeline_run(submission):
            captured_submission["obj"] = submission
            return mock_execution

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", side_effect=lambda fn, sub: capture_pipeline_run(sub)), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            request = GradingRequest(
                submission_id=1,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="u1",
                submission_files={
                    "main.py": {
                        "filename": "main.py",
                        "content": "x = 1",
                        "changed_lines": None,
                        "file_metadata": None,
                    }
                },
                evaluation_scope={"scoped_files": ["main.py"]},
            )
            await grade_submission(request)

            sub = captured_submission["obj"]
            assert sub.evaluation_scope is not None
            assert sub.evaluation_scope.scoped_files == ["main.py"]

    @pytest.mark.asyncio
    async def test_grading_service_hydrates_changed_lines(self):
        """GradingRequest with changed_lines in files → SubmissionFile has set(changed_lines)."""
        mock_result = Mock()
        mock_result.final_score = 100.0
        mock_result.feedback = None
        mock_result.result_tree = None
        mock_result.focus = Mock()
        mock_result.focus.to_dict = Mock(return_value={"base": []})
        mock_result.comparison = None

        mock_execution = Mock()
        mock_execution.result = mock_result
        mock_execution.start_time = time.time()
        mock_execution.step_results = []

        mock_submission_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_submission_repo.update = AsyncMock()

        mock_result_repo = Mock()
        mock_result_repo.create = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        captured_submission = {}

        def capture_pipeline_run(submission):
            captured_submission["obj"] = submission
            return mock_execution

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", side_effect=lambda fn, sub: capture_pipeline_run(sub)), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            request = GradingRequest(
                submission_id=2,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="u2",
                submission_files={
                    "main.py": {
                        "filename": "main.py",
                        "content": "x = 1",
                        "changed_lines": [1, 3, 5],
                        "file_metadata": {"change_status": "modified"},
                    }
                },
            )
            await grade_submission(request)

            sub = captured_submission["obj"]
            main_file = sub.submission_files["main.py"]
            assert main_file.changed_lines == {1, 3, 5}
            assert main_file.metadata == {"change_status": "modified"}
            assert main_file.is_contribution_aware is True

    @pytest.mark.asyncio
    async def test_grading_service_evaluation_scope_none_when_absent(self):
        """GradingRequest without evaluation_scope → submission.evaluation_scope is None."""
        mock_result = Mock()
        mock_result.final_score = 100.0
        mock_result.feedback = None
        mock_result.result_tree = None
        mock_result.focus = Mock()
        mock_result.focus.to_dict = Mock(return_value={"base": []})
        mock_result.comparison = None

        mock_execution = Mock()
        mock_execution.result = mock_result
        mock_execution.start_time = time.time()
        mock_execution.step_results = []

        mock_submission_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_submission_repo.update = AsyncMock()

        mock_result_repo = Mock()
        mock_result_repo.create = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        captured_submission = {}

        def capture_pipeline_run(submission):
            captured_submission["obj"] = submission
            return mock_execution

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", side_effect=lambda fn, sub: capture_pipeline_run(sub)), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            request = GradingRequest(
                submission_id=3,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="u3",
                submission_files={
                    "main.py": {
                        "filename": "main.py",
                        "content": "x = 1",
                    }
                },
                evaluation_scope=None,
            )
            await grade_submission(request)

            sub = captured_submission["obj"]
            assert sub.evaluation_scope is None
            main_file = sub.submission_files["main.py"]
            assert main_file.changed_lines is None
            assert main_file.is_contribution_aware is False

    @pytest.mark.asyncio
    async def test_grading_service_changed_lines_none_when_absent(self):
        """GradingRequest with file missing changed_lines key → SubmissionFile.changed_lines is None."""
        mock_result = Mock()
        mock_result.final_score = 100.0
        mock_result.feedback = None
        mock_result.result_tree = None
        mock_result.focus = Mock()
        mock_result.focus.to_dict = Mock(return_value={"base": []})
        mock_result.comparison = None

        mock_execution = Mock()
        mock_execution.result = mock_result
        mock_execution.start_time = time.time()
        mock_execution.step_results = []

        mock_submission_repo = Mock()
        mock_submission_repo.update_status = AsyncMock()
        mock_submission_repo.update = AsyncMock()

        mock_result_repo = Mock()
        mock_result_repo.create = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        captured_submission = {}

        def capture_pipeline_run(submission):
            captured_submission["obj"] = submission
            return mock_execution

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", side_effect=lambda fn, sub: capture_pipeline_run(sub)), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            # Simulate the minimal storage format (no changed_lines or file_metadata keys)
            request = GradingRequest(
                submission_id=4,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="u4",
                submission_files={
                    "main.py": {
                        "filename": "main.py",
                        "content": "x = 1",
                    }
                },
            )
            await grade_submission(request)

            sub = captured_submission["obj"]
            main_file = sub.submission_files["main.py"]
            assert main_file.changed_lines is None
            assert main_file.metadata is None
