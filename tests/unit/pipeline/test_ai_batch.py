"""AI batching returns explicit assessments; providers remain stateless."""

import pytest
from autograder.models.evaluation_error import EvaluationError
from typing import Dict, List, Optional
import autograder.utils.executors.ai_executor as ai_executor_mod
from unittest.mock import MagicMock

from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.test_function import TestFunction
from autograder.models.criteria_tree import (
    CategoryNode,
    CriteriaTree,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import (
    Submission,
    SubmissionFile,
)
from autograder.models.dataclass.test_result import TestResult
from autograder.services.grader.grader_service import GraderService
from autograder.services.ai_batch import evaluate_ai_batch
from execution_host.openai_provider import AiExecutor, TestInput, TestOutput


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_submission(files: Optional[Dict[str, str]] = None) -> Submission:
    files = files or {"main.py": "print('hello')"}
    return Submission(
        username="test",
        user_id=1,
        assignment_id=1,
        submission_files={
            name: SubmissionFile(filename=name, content=content)
            for name, content in files.items()
        },
    )


# ---------------------------------------------------------------------------
# Concrete AiTestFunction for tests
# ---------------------------------------------------------------------------

class _ConcreteAiTest(AiTestFunction):
    """Minimal concrete AiTestFunction used in tests."""

    @property
    def name(self) -> str:
        return "ai_code_review"

    @property
    def description(self) -> str:
        return "AI code review"

    @property
    def parameter_description(self) -> List[ParamDescription]:
        return []

    def build_prompt(self, files, **kwargs) -> str:
        return "Evaluate the code quality."


# ---------------------------------------------------------------------------
# AiTestFunction ABC tests
# ---------------------------------------------------------------------------

class TestAiTestFunctionPreComputedPath:
    """Tests for AiTestFunction pre-computed results lookup and fallback path."""

    def test_returns_precomputed_result_when_present(self):
        """Pre-computed result for this test's name is returned directly."""
        func = _ConcreteAiTest()
        expected = TestResult(
            test_name="ai_code_review", score=85.0, report="Good work.", subject_name=""
        )
        pre_computed = {"ai_code_review": expected}

        result = func.execute(files=[], sandbox=None, criterion_id="ai_code_review", pre_computed_results=pre_computed)

        assert result is expected

    def test_missing_precomputed_result_does_not_retry(self):
        func = _ConcreteAiTest()
        with pytest.raises(EvaluationError, match="required AI assessment"):
            func.execute(files=[], sandbox=None, criterion_id="ai_code_review", pre_computed_results={"other": TestResult("x", 100, "")})

    def test_standalone_requires_host_provider(self):
        with pytest.raises(EvaluationError, match="host-supplied"):
            _ConcreteAiTest().execute(files=None, sandbox=None, criterion_id="ai_code_review")


# ---------------------------------------------------------------------------
# AI batch assessments
# ---------------------------------------------------------------------------

def _build_criteria_tree_with_ai_test(ai_test_func: AiTestFunction, test_name="ai_test_1") -> CriteriaTree:
    test_node = TestNode(
        name=test_name,
        criterion_id=ai_test_func.name,
        test_function=ai_test_func,
        parameters={},
    )
    subject = SubjectNode(name="Main", weight=100, tests=[test_node])
    base = CategoryNode(name="base", weight=100, subjects=[subject])
    return CriteriaTree(base=base)


def _build_criteria_tree_no_ai() -> CriteriaTree:
    """A simple criteria tree with a regular (non-AI) test function."""

    class _RegularTest(TestFunction):
        @property
        def name(self):
            return "regular"

        @property
        def description(self):
            return "Regular"

        @property
        def parameter_description(self):
            return []

        def execute(self, files, sandbox, *args, **kwargs):
            return TestResult(test_name="regular", score=100, report="ok", subject_name="")

    test_node = TestNode(name="reg_test", test_function=_RegularTest())
    base = CategoryNode(name="base", weight=100, tests=[test_node])
    return CriteriaTree(base=base)


class TestAiBatch:
    def test_skips_provider_when_no_ai_tests(self):
        provider = MagicMock()
        assert evaluate_ai_batch(_build_criteria_tree_no_ai(), _make_submission(), provider) == {}
        provider.run.assert_not_called()

    def test_returns_assessments_and_sends_context(self):
        provider = MagicMock()
        expected = TestResult("ai_code_review", 90, "Nice")
        provider.run.return_value = {"ai_code_review": expected}
        result = evaluate_ai_batch(_build_criteria_tree_with_ai_test(_ConcreteAiTest()),
                                   _make_submission({"main.py": "code"}), provider)
        assert result["ai_code_review"] is expected
        inputs, files, locale = provider.run.call_args.args
        assert [item.test_name for item in inputs] == ["ai_code_review"]
        assert files == {"main.py": "code"}
        assert locale == "en"

    @pytest.mark.parametrize("results", [{}, {"unknown": TestResult("unknown", 50, "")}])
    def test_missing_or_unexpected_output_fails_without_retry(self, results):
        provider = MagicMock()
        provider.run.return_value = results
        with pytest.raises(EvaluationError, match="required AI assessment"):
            evaluate_ai_batch(_build_criteria_tree_with_ai_test(_ConcreteAiTest()),
                              _make_submission(), provider)
        provider.run.assert_called_once()


# ---------------------------------------------------------------------------
# GraderService tests
# ---------------------------------------------------------------------------

class TestGraderServicePreComputedResults:
    """GraderService must thread pre_computed_results through to test functions."""

    def test_pre_computed_results_forwarded_to_test_function(self):
        """GraderService passes pre_computed_results as a kwarg to test_function.execute."""
        received_kwargs = {}

        class _CapturingTest(TestFunction):
            @property
            def name(self):
                return "capture"

            @property
            def description(self):
                return ""

            @property
            def parameter_description(self):
                return []

            def execute(self, files, sandbox, *args, **kwargs):
                received_kwargs.update(kwargs)
                return TestResult(test_name="capture", score=50, report="", subject_name="")

        test_node = TestNode(name="cap_test", test_function=_CapturingTest())
        base = CategoryNode(name="base", weight=100, tests=[test_node])
        tree = CriteriaTree(base=base)

        svc = GraderService()
        precomp = {"capture": TestResult("capture", 99, "precomp", "")}

        svc.grade_from_tree(
            criteria_tree=tree,
            submission_files={},
            pre_computed_results=precomp,
        )

        assert received_kwargs.get("pre_computed_results") is precomp

    def test_no_executor_attribute_checked(self):
        """GraderService must not inspect test_function.executor."""

        class _TestWithExecutorAttr(TestFunction):
            """Simulate old-style test that had an `executor` attribute."""

            executor = MagicMock()  # should be completely ignored

            @property
            def name(self):
                return "old_style"

            @property
            def description(self):
                return ""

            @property
            def parameter_description(self):
                return []

            def execute(self, files, sandbox, *args, **kwargs):
                return TestResult(test_name="old_style", score=100, report="ok", subject_name="")

        test_node = TestNode(name="old_test", test_function=_TestWithExecutorAttr())
        base = CategoryNode(name="base", weight=100, tests=[test_node])
        tree = CriteriaTree(base=base)

        svc = GraderService()
        # Should complete without calling executor.stop()
        _ = svc.grade_from_tree(criteria_tree=tree, submission_files={})

        # The executor.stop() should never have been called
        _TestWithExecutorAttr.executor.stop.assert_not_called()


# ---------------------------------------------------------------------------
# AiExecutor stateless contract
# ---------------------------------------------------------------------------

class TestAiExecutorStateless:
    """AiExecutor.run() must be stateless: no global singleton, no mutation."""

    def test_run_returns_empty_dict_on_empty_test_list(self):
        """run() returns an empty dict immediately when no tests are provided."""
        executor = AiExecutor.__new__(AiExecutor)  # skip __init__ (avoids API key lookup)
        # Patch the client attribute so no real API call happens
        executor.client = MagicMock()

        result = executor.run(tests=[], submission_files={})
        assert not result
        executor.client.responses.parse.assert_not_called()

    def test_two_instances_are_independent(self):
        """Verify there is no module-level singleton that could bleed state."""
        assert not hasattr(ai_executor_mod, "ai_executor"), (
            "Module-level 'ai_executor' singleton must have been removed."
        )

    def test_outputs_to_results_maps_by_title(self):
        """_outputs_to_results builds a dict keyed by test name using output titles."""
        inputs = [TestInput(test_name="t1", prompt="p1"), TestInput(test_name="t2", prompt="p2")]
        outputs = [
            TestOutput(title="t1", feedback="fb1", subject="s1", score=80.0),
            TestOutput(title="t2", feedback="fb2", subject="s2", score=60.0),
        ]

        mapping = AiExecutor._outputs_to_results(inputs, outputs)  # pylint: disable=protected-access

        assert "t1" in mapping
        assert mapping["t1"].score == 80.0
        assert mapping["t1"].report == "fb1"
        assert "t2" in mapping
        assert mapping["t2"].score == 60.0

    def test_outputs_to_results_rejects_unknown_titles(self):
        inputs = [TestInput(test_name="t1", prompt="p")]
        outputs = [TestOutput(title="unknown_test", feedback="fb", subject="s", score=50)]
        with pytest.raises(EvaluationError):
            AiExecutor._outputs_to_results(inputs, outputs)

    @pytest.mark.parametrize("outputs", [[], [TestOutput(title="t1", feedback="", subject="", score=50)] * 2])
    def test_outputs_reject_missing_and_duplicate_assessments(self, outputs):
        with pytest.raises(EvaluationError):
            AiExecutor._outputs_to_results([TestInput(test_name="t1", prompt="p")], outputs)
