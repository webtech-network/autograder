"""
Integration tests for ResultComparator with the grading pipeline.

Tests cover:
1. Comparing two real pipeline executions (static_analysis template, no sandbox)
2. Comparison via the grading service when baseline_result_tree is provided
3. Round-trip: pipeline produces ResultTree → to_dict → from_dict → compare
4. Focus + Comparison co-existence on GradingResult
5. Edge case: baseline_result_tree provided but pipeline fails → comparison skipped
"""

import time
import pytest
from unittest.mock import AsyncMock, Mock, patch

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    RootResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.services.result_comparator import ResultComparator
from web.service.grading_service import GradingRequest, grade_submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_static_analysis_submission(
    code: str,
    user_id: str = "integration-user",
    assignment_id: int = 1,
) -> Submission:
    """Build a Submission for static_analysis tests (no sandbox needed)."""
    return Submission(
        username="integration-student",
        user_id=user_id,
        assignment_id=assignment_id,
        submission_files={"main.py": SubmissionFile(filename="main.py", content=code)},
        language=None,  # static_analysis doesn't require language
        locale="en",
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


def _build_result_tree(
    tests: list[tuple[str, float]],
    final_score: float | None = None,
) -> ResultTree:
    """Build a minimal ResultTree from a list of (name, score) tuples."""
    test_nodes = [
        TestResultNode(name=name, score=score, report="", test_node=None, weight=100.0)
        for name, score in tests
    ]
    base = CategoryResultNode(
        name="base",
        weight=100.0,
        subjects=[SubjectResultNode(name="s1", weight=100.0, tests=test_nodes)],
    )
    root = RootResultNode(
        name="root",
        base=base,
        score=final_score if final_score is not None else 0.0,
    )
    tree = ResultTree(root=root)
    if final_score is None:
        tree.calculate_final_score()
    return tree


# ---------------------------------------------------------------------------
# Integration: Pipeline → ResultComparator
# ---------------------------------------------------------------------------


class TestPipelineComparisonIntegration:
    """Compare ResultTrees produced by two real pipeline executions."""

    def test_compare_clean_vs_violation_submission(self):
        """Run pipeline twice with different code and compare result trees."""
        criteria = _static_analysis_criteria(["os", "sys"])

        # Baseline: clean code (no violations)
        pipeline_clean = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        exec_clean = pipeline_clean.run(
            _make_static_analysis_submission("x = 42\nprint(x)")
        )
        assert exec_clean.result is not None
        baseline_tree = exec_clean.result.result_tree

        # Head: code with one violation
        pipeline_violation = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        )
        exec_violation = pipeline_violation.run(
            _make_static_analysis_submission("import os\nprint(os.getcwd())")
        )
        assert exec_violation.result is not None
        head_tree = exec_violation.result.result_tree

        # Compare
        comparison = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert comparison.score_delta < 0, "Introducing violations should lower the score"
        assert comparison.improved is False
        assert len(comparison.test_deltas) >= 2

        # The os-related test should have regressed
        deltas_by_path = {d.path: d for d in comparison.test_deltas}
        os_delta = next(
            (d for d in comparison.test_deltas if "no_os" in d.path), None
        )
        assert os_delta is not None
        assert os_delta.status == "regressed"

    def test_compare_identical_submissions(self):
        """Two identical submissions should produce unchanged deltas."""
        criteria = _static_analysis_criteria(["os"])
        code = "x = 42\nprint(x)"

        exec1 = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code, user_id="u1"))

        exec2 = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code, user_id="u2"))

        comparison = ResultComparator.compare(
            baseline=exec1.result.result_tree,
            head=exec2.result.result_tree,
        )

        assert comparison.score_delta == 0.0
        assert comparison.improved is False
        for delta in comparison.test_deltas:
            assert delta.status == "unchanged"

    def test_compare_violation_fixed(self):
        """Fixing a violation should produce a positive delta."""
        criteria = _static_analysis_criteria(["os"])

        exec_baseline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("import os\nprint(os.getcwd())"))

        exec_head = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("print('no imports')"))

        comparison = ResultComparator.compare(
            baseline=exec_baseline.result.result_tree,
            head=exec_head.result.result_tree,
        )

        assert comparison.score_delta > 0
        assert comparison.improved is True


# ---------------------------------------------------------------------------
# Integration: ResultTree serialization round-trip through comparison
# ---------------------------------------------------------------------------


class TestSerializationRoundTripComparison:
    """Verify comparison works across serialized/deserialized ResultTrees."""

    def test_round_trip_preserves_comparison_semantics(self):
        """Serialize tree → deserialize → compare should match direct compare."""
        baseline = _build_result_tree([("t1", 50.0), ("t2", 100.0)])
        head = _build_result_tree([("t1", 80.0), ("t2", 60.0)])

        # Direct comparison
        direct = ResultComparator.compare(baseline=baseline, head=head)

        # Round-trip both trees through serialization
        baseline_rt = ResultTree.from_dict(baseline.to_dict())
        head_rt = ResultTree.from_dict(head.to_dict())
        round_tripped = ResultComparator.compare(baseline=baseline_rt, head=head_rt)

        assert direct.score_delta == round_tripped.score_delta
        assert direct.improved == round_tripped.improved
        assert len(direct.test_deltas) == len(round_tripped.test_deltas)
        for d_delta, rt_delta in zip(direct.test_deltas, round_tripped.test_deltas):
            assert d_delta.path == rt_delta.path
            assert d_delta.status == rt_delta.status
            assert d_delta.delta == rt_delta.delta

    def test_db_format_baseline_comparison(self):
        """Simulate the DB-stored format used in grading_service.py."""
        # Simulate baseline stored in DB (the children wrapper format)
        db_baseline = {
            "final_score": 75.0,
            "children": {
                "name": "root",
                "score": 75.0,
                "base": {
                    "name": "base",
                    "weight": 100.0,
                    "score": 75.0,
                    "subjects": [
                        {
                            "name": "checks",
                            "weight": 100.0,
                            "score": 75.0,
                            "tests": [
                                {"name": "t1", "score": 50.0, "weight": 50.0},
                                {"name": "t2", "score": 100.0, "weight": 50.0},
                            ],
                        }
                    ],
                },
            },
        }

        baseline_tree = ResultTree.from_dict(db_baseline)

        # Head tree using the same subject name "checks" as the baseline
        head_test_nodes = [
            TestResultNode(name="t1", score=100.0, report="", test_node=None, weight=50.0),
            TestResultNode(name="t2", score=100.0, report="", test_node=None, weight=50.0),
        ]
        head_base = CategoryResultNode(
            name="base",
            weight=100.0,
            subjects=[SubjectResultNode(name="checks", weight=100.0, tests=head_test_nodes)],
        )
        head_root = RootResultNode(name="root", base=head_base, score=100.0)
        head_tree = ResultTree(root=head_root)

        comparison = ResultComparator.compare(baseline=baseline_tree, head=head_tree)
        assert comparison.score_delta == 25.0
        assert comparison.improved is True

        # t1 improved (50 → 100), t2 unchanged (100 → 100)
        deltas_by_path = {d.path: d for d in comparison.test_deltas}
        assert deltas_by_path["base/checks/t1"].status == "improved"
        assert deltas_by_path["base/checks/t1"].delta == 50.0
        assert deltas_by_path["base/checks/t2"].status == "unchanged"
        assert deltas_by_path["base/checks/t2"].delta == 0.0


# ---------------------------------------------------------------------------
# Integration: GradingService with baseline comparison
# ---------------------------------------------------------------------------


class TestGradingServiceComparison:
    """Test the grading service's baseline comparison flow."""

    @pytest.mark.asyncio
    async def test_grading_service_performs_comparison_when_baseline_provided(self):
        """Verify grading_service attaches comparison to result when baseline given."""
        # Build a real baseline result tree dict (as would come from a previous result)
        baseline = _build_result_tree([("no_os", 100.0)])
        baseline_dict = baseline.to_dict()

        # Mock the pipeline execution with a result tree
        mock_result = Mock()
        mock_result.final_score = 0.0
        mock_result.feedback = None
        mock_result.result_tree = _build_result_tree([("no_os", 0.0)])
        mock_result.focus = Mock()
        mock_result.focus.to_dict = Mock(return_value={"base": []})
        mock_result.comparison = None  # Will be set by grading_service

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

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", return_value=mock_execution), \
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
                submission_files={"main.py": {"filename": "main.py", "content": "import os"}},
                baseline_result_tree=baseline_dict,
            )
            await grade_submission(request)

            # The comparison should have been set on the result
            assert mock_result.comparison is not None
            assert mock_result.comparison.score_delta == -100.0
            assert mock_result.comparison.improved is False

            # Verify the comparison dict was persisted
            create_call = mock_result_repo.create.call_args[1]
            assert create_call["comparison"] is not None
            assert create_call["comparison"]["score_delta"] == -100.0

    @pytest.mark.asyncio
    async def test_grading_service_skips_comparison_when_no_baseline(self):
        """Verify no comparison is computed when baseline_result_tree is None."""
        mock_result = Mock()
        mock_result.final_score = 100.0
        mock_result.feedback = None
        mock_result.result_tree = _build_result_tree([("t1", 100.0)])
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

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", return_value=mock_execution), \
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
                submission_files={"main.py": {"filename": "main.py", "content": "x = 1"}},
                baseline_result_tree=None,
            )
            await grade_submission(request)

            # comparison should remain None
            assert mock_result.comparison is None
            create_call = mock_result_repo.create.call_args[1]
            assert create_call["comparison"] is None

    @pytest.mark.asyncio
    async def test_grading_service_handles_malformed_baseline_gracefully(self):
        """Verify malformed baseline_result_tree doesn't crash the pipeline."""
        mock_result = Mock()
        mock_result.final_score = 80.0
        mock_result.feedback = None
        mock_result.result_tree = _build_result_tree([("t1", 80.0)])
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

        with patch("web.service.grading_service.build_pipeline") as mock_build, \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", return_value=mock_execution), \
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
                submission_files={"main.py": {"filename": "main.py", "content": "x = 1"}},
                baseline_result_tree={"garbage": "data"},  # Malformed
            )
            # Should NOT raise — the service catches exceptions on comparison
            await grade_submission(request)

            # comparison should remain None because from_dict will fail
            assert mock_result.comparison is None
            # But the result should still be persisted successfully
            assert mock_result_repo.create.called


# ---------------------------------------------------------------------------
# Integration: Focus + Comparison coexistence
# ---------------------------------------------------------------------------


class TestFocusAndComparisonCoexistence:
    """Verify Focus and ComparisonResult coexist correctly on GradingResult."""

    def test_pipeline_produces_focus_and_comparison_can_attach(self):
        """Pipeline produces focus; comparison can be attached post-pipeline."""
        criteria = _static_analysis_criteria(["os"])

        # Run baseline
        exec_baseline = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("import os"))

        # Run head
        exec_head = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("x = 1"))

        result = exec_head.result
        assert result is not None
        assert result.focus is not None, "Pipeline should produce Focus"
        assert result.comparison is None, "Pipeline doesn't compute comparison"

        # Attach comparison (as grading_service does)
        result.comparison = ResultComparator.compare(
            baseline=exec_baseline.result.result_tree,
            head=exec_head.result.result_tree,
        )

        assert result.comparison is not None
        assert result.comparison.improved is True
        assert result.focus is not None  # Focus still intact

    def test_comparison_result_serializes_alongside_focus(self):
        """Both focus.to_dict() and comparison.to_dict() work on the same GradingResult."""
        criteria = _static_analysis_criteria(["os", "sys"])

        exec_base = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("import os\nimport sys"))

        exec_head = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("x = 1"))

        grading_result = exec_head.result
        grading_result.comparison = ResultComparator.compare(
            baseline=exec_base.result.result_tree,
            head=exec_head.result.result_tree,
        )

        # Both should serialize without error
        focus_dict = grading_result.focus.to_dict()
        comparison_dict = grading_result.comparison.to_dict()

        assert "base" in focus_dict
        assert "score_delta" in comparison_dict
        assert "test_deltas" in comparison_dict
        assert isinstance(comparison_dict["test_deltas"], list)


# ---------------------------------------------------------------------------
# Integration: Score Vector via pipeline and grading service
# ---------------------------------------------------------------------------


class TestScoreVectorIntegration:
    """Verify score_vector is correctly produced by the pipeline and persisted."""

    def test_pipeline_result_tree_produces_correct_score_vector(self):
        """Run a real pipeline and verify to_score_vector() returns correct paths and scores."""
        criteria = _static_analysis_criteria(["os", "sys"])
        code = "import os\nx = 1"  # violates os, passes sys

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        assert execution.result is not None
        result_tree = execution.result.result_tree
        assert result_tree is not None

        sv = result_tree.to_score_vector()

        # Should have exactly 2 test entries
        assert len(sv) == 2

        # All keys should be strings, all values should be floats
        for key, value in sv.items():
            assert isinstance(key, str)
            assert isinstance(value, (int, float))

        # The os test should have failed (< 100), sys test should have passed (100)
        os_entry = next((v for k, v in sv.items() if "no_os" in k), None)
        sys_entry = next((v for k, v in sv.items() if "no_sys" in k), None)
        assert os_entry is not None and os_entry < 100.0
        assert sys_entry is not None and sys_entry == 100.0

    def test_pipeline_failure_produces_no_score_vector(self):
        """Invalid criteria cause pipeline failure → no result_tree, no score_vector."""
        criteria = {"base": {"weight": 100.0, "tests": []}}  # Invalid: no tests

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission("x = 1"))

        # Pipeline should fail — result is None, no score_vector possible
        assert execution.result is None

    def test_score_vector_is_deterministic_across_runs(self):
        """Same code + criteria should produce identical score_vector."""
        criteria = _static_analysis_criteria(["os"])
        code = "import os"

        sv1 = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code, user_id="u1")).result.result_tree.to_score_vector()

        sv2 = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code, user_id="u2")).result.result_tree.to_score_vector()

        assert sv1 == sv2

    @pytest.mark.asyncio
    async def test_grading_service_persists_score_vector(self):
        """Verify grading service passes score_vector to result_repo.create()."""
        # Build a real result tree so to_score_vector() works
        result_tree = _build_result_tree([("t1", 80.0), ("t2", 100.0)])

        mock_result = Mock()
        mock_result.final_score = 90.0
        mock_result.feedback = None
        mock_result.result_tree = result_tree
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

        with patch("web.service.grading_service.build_pipeline"), \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", return_value=mock_execution), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            request = GradingRequest(
                submission_id=10,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="sv-user",
                submission_files={"main.py": {"filename": "main.py", "content": "x = 1"}},
                baseline_result_tree=None,
            )
            await grade_submission(request)

            create_call = mock_result_repo.create.call_args[1]
            persisted_sv = create_call["score_vector"]

            # Should match what to_score_vector() returns
            expected_sv = result_tree.to_score_vector()
            assert persisted_sv == expected_sv
            assert len(persisted_sv) == 2
            assert all(isinstance(v, (int, float)) for v in persisted_sv.values())

    @pytest.mark.asyncio
    async def test_grading_service_score_vector_none_when_no_result_tree(self):
        """score_vector should be None when pipeline fails and result_tree is None."""
        mock_result = Mock()
        mock_result.final_score = 0.0
        mock_result.feedback = None
        mock_result.result_tree = None  # No result tree
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

        with patch("web.service.grading_service.build_pipeline"), \
             patch("web.service.grading_service.get_session") as mock_get_session, \
             patch("asyncio.to_thread", return_value=mock_execution), \
             patch("web.service.grading_service.SubmissionRepository", return_value=mock_submission_repo), \
             patch("web.service.grading_service.ResultRepository", return_value=mock_result_repo), \
             patch("web.service.grading_service.PipelineExecutionSerializer") as mock_serializer:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_serializer.serialize.return_value = {"status": "success"}

            request = GradingRequest(
                submission_id=11,
                grading_config_id=1,
                template_name="static_analysis",
                criteria_config={},
                setup_config={},
                feedback_config={},
                include_feedback=False,
                language="python",
                username="student",
                external_user_id="sv-none-user",
                submission_files={"main.py": {"filename": "main.py", "content": "x = 1"}},
            )
            await grade_submission(request)

            create_call = mock_result_repo.create.call_args[1]
            assert create_call["score_vector"] is None


# ---------------------------------------------------------------------------
# Integration: FocusService refactor — diff_score correctness via pipeline
# ---------------------------------------------------------------------------


class TestFocusServiceRefactorIntegration:
    """Verify FocusService produces correct diff_score values through the refactored
    iter_test_results(prefix, parent_multiplier) traversal on real pipeline results."""

    def test_focus_diff_scores_on_real_pipeline(self):
        """Run a pipeline with violations and verify focus diff_score values are non-zero."""
        criteria = _static_analysis_criteria(["os", "sys"])
        code = "import os\nimport sys"  # both fail

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        assert execution.result is not None
        focus = execution.result.focus
        assert focus is not None
        assert focus.base is not None
        assert len(focus.base) >= 2

        # All tests failed → all should have diff_score > 0
        for ft in focus.base:
            assert ft.diff_score > 0, (
                f"Test {ft.test_result.name} has diff_score {ft.diff_score}, expected > 0"
            )

        # Focus should be sorted by diff_score descending
        diff_scores = [ft.diff_score for ft in focus.base]
        assert diff_scores == sorted(diff_scores, reverse=True)

    def test_focus_passing_tests_have_zero_diff_score(self):
        """Passing tests (score=100) should have diff_score = 0."""
        criteria = _static_analysis_criteria(["os"])
        code = "x = 42"  # no violations

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        focus = execution.result.focus
        for ft in focus.base:
            assert ft.diff_score == 0.0, (
                f"Passing test {ft.test_result.name} should have diff_score 0, got {ft.diff_score}"
            )

    def test_focus_diff_score_sums_to_points_lost(self):
        """Sum of diff_scores should equal total points lost from 100."""
        criteria = _static_analysis_criteria(["os", "sys"])
        code = "import os\nimport sys"

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        focus = execution.result.focus
        final_score = execution.result.final_score
        total_diff = sum(ft.diff_score for ft in focus.base)

        # Total diff_score should approximate points lost (100 - final_score)
        # Allow small floating point tolerance
        points_lost = 100.0 - final_score
        assert abs(total_diff - points_lost) < 0.01, (
            f"Sum of diff_scores ({total_diff}) should equal points lost ({points_lost})"
        )

    def test_focus_and_score_vector_paths_are_consistent(self):
        """Focus and score_vector should reference the same test paths."""
        criteria = _static_analysis_criteria(["os", "sys"])
        code = "import os"

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        result_tree = execution.result.result_tree
        focus = execution.result.focus

        sv_paths = set(result_tree.to_score_vector().keys())

        # Collect all test names from focus and find them in score_vector paths
        focus_test_names = {ft.test_result.name for ft in focus.base}
        sv_test_names = {path.rsplit("/", 1)[-1] for path in sv_paths}

        # Every focus test name should appear in score_vector paths
        assert focus_test_names == sv_test_names, (
            f"Focus test names {focus_test_names} should match "
            f"score_vector test names {sv_test_names}"
        )

    def test_focus_serialization_after_pipeline(self):
        """Focus.to_dict() should produce valid serializable output from real pipeline."""
        criteria = _static_analysis_criteria(["os"])
        code = "import os"

        execution = build_pipeline(
            template_name="static_analysis",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config={},
        ).run(_make_static_analysis_submission(code))

        focus_dict = execution.result.focus.to_dict()

        assert "base" in focus_dict
        assert isinstance(focus_dict["base"], list)
        assert len(focus_dict["base"]) >= 1

        for entry in focus_dict["base"]:
            assert "test_result" in entry
            assert "diff_score" in entry
            assert isinstance(entry["diff_score"], (int, float))
            assert "name" in entry["test_result"]
            assert "score" in entry["test_result"]

        # penalty and bonus should be None (not used in static_analysis)
        assert focus_dict["penalty"] is None
        assert focus_dict["bonus"] is None

