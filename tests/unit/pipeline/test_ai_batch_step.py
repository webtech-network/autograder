"""
Unit tests for the AI-batch pipeline redesign.

Covers:
- AiTestFunction ABC: pre_computed_results lookup and fallback path
- AiBatchStep: skip when no AI tests, collect and forward batch results
- GraderService: pre_computed_results forwarded to test functions
- GradeStep: picks up AI_BATCH results and passes them through
"""

from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.step import Step
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.criteria_tree import (
    CategoryNode,
    CriteriaTree,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.grader_service import GraderService
from autograder.steps.ai_batch_step import AiBatchStep
from autograder.steps.grade_step import GradeStep


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


def _make_pipeline_exec(submission: Optional[Submission] = None) -> PipelineExecution:
    return PipelineExecution.start_execution(submission or _make_submission())


def _inject_step_result(pipeline_exec: PipelineExecution, step_name: StepName, data) -> PipelineExecution:
    return pipeline_exec.add_step_result(
        StepResult(step=step_name, data=data, status=StepStatus.SUCCESS)
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
    def test_returns_precomputed_result_when_present(self):
        func = _ConcreteAiTest()
        expected = TestResult(
            test_name="ai_code_review", score=85.0, report="Good work.", subject_name=""
        )
        pre_computed = {"ai_code_review": expected}

        result = func.execute(files=[], sandbox=None, pre_computed_results=pre_computed)

        assert result is expected

    def test_ignores_precomputed_for_other_tests(self):
        """If the dict has results for other tests, this test's fallback is invoked."""
        func = _ConcreteAiTest()
        pre_computed = {"some_other_test": TestResult("x", 100, "", "")}

        # The fallback (_run_single) makes an API call; we patch AiExecutor.run
        # to return an empty dict, which triggers the "no result" guard.
        with patch(
            "autograder.utils.executors.ai_executor.AiExecutor"
        ) as MockExecutor:
            MockExecutor.return_value.run.return_value = {}
            result = func.execute(files=[], sandbox=None, pre_computed_results=pre_computed)

        assert result.test_name == "ai_code_review"
        assert result.score == 0
        assert "no result" in result.report.lower()

    def test_fallback_called_when_no_precomputed(self):
        func = _ConcreteAiTest()
        fallback_result = TestResult(
            test_name="ai_code_review", score=70.0, report="Fallback.", subject_name=""
        )

        with patch(
            "autograder.utils.executors.ai_executor.AiExecutor"
        ) as MockExecutor:
            MockExecutor.return_value.run.return_value = {"ai_code_review": fallback_result}
            result = func.execute(files=[], sandbox=None)

        assert result is fallback_result

    def test_fallback_returns_zero_result_on_empty_api_response(self):
        func = _ConcreteAiTest()

        with patch(
            "autograder.utils.executors.ai_executor.AiExecutor"
        ) as MockExecutor:
            MockExecutor.return_value.run.return_value = {}
            result = func.execute(files=None, sandbox=None)

        assert result.score == 0
        assert result.test_name == "ai_code_review"


# ---------------------------------------------------------------------------
# AiBatchStep tests
# ---------------------------------------------------------------------------

def _build_criteria_tree_with_ai_test(ai_test_func: AiTestFunction, test_name="ai_test_1") -> CriteriaTree:
    test_node = TestNode(
        name=test_name,
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

        def execute(self, files, sandbox, **kwargs):
            return TestResult(test_name="regular", score=100, report="ok", subject_name="")

    test_node = TestNode(name="reg_test", test_function=_RegularTest())
    base = CategoryNode(name="base", weight=100, tests=[test_node])
    return CriteriaTree(base=base)


class TestAiBatchStep:
    def test_skips_gracefully_when_no_ai_tests(self):
        step = AiBatchStep()
        tree = _build_criteria_tree_no_ai()
        pipeline_exec = _make_pipeline_exec()
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        result_exec = step.execute(pipeline_exec)

        assert result_exec.has_step_result(StepName.AI_BATCH)
        ai_result = result_exec.get_step_result(StepName.AI_BATCH)
        assert ai_result.status == StepStatus.SUCCESS
        assert ai_result.data == {}

    def test_collects_ai_tests_and_calls_executor(self):
        ai_func = _ConcreteAiTest()
        tree = _build_criteria_tree_with_ai_test(ai_func)
        submission = _make_submission({"main.py": "code"})
        pipeline_exec = _make_pipeline_exec(submission)
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        expected_ai_result = TestResult(
            test_name="ai_code_review", score=90.0, report="Nice.", subject_name=""
        )

        with patch(
            "autograder.steps.ai_batch_step.AiExecutor"
        ) as MockExecutor:
            MockExecutor.return_value.run.return_value = {"ai_code_review": expected_ai_result}
            result_exec = AiBatchStep().execute(pipeline_exec)

        assert result_exec.has_step_result(StepName.AI_BATCH)
        data: Dict[str, TestResult] = result_exec.get_step_result(StepName.AI_BATCH).data
        assert data["ai_code_review"] is expected_ai_result

    def test_executor_called_with_correct_files(self):
        ai_func = _ConcreteAiTest()
        tree = _build_criteria_tree_with_ai_test(ai_func)
        submission = _make_submission({"main.py": "my code"})
        pipeline_exec = _make_pipeline_exec(submission)
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        with patch("autograder.steps.ai_batch_step.AiExecutor") as MockExecutor:
            MockExecutor.return_value.run.return_value = {}
            AiBatchStep().execute(pipeline_exec)

        _executor_instance = MockExecutor.return_value
        call_args = _executor_instance.run.call_args
        # Second positional arg is the submission_files dict
        files_passed = call_args[0][1]
        assert "main.py" in files_passed
        assert files_passed["main.py"] == "my code"

    def test_step_result_stored_in_pipeline(self):
        ai_func = _ConcreteAiTest()
        tree = _build_criteria_tree_with_ai_test(ai_func)
        pipeline_exec = _make_pipeline_exec()
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        with patch("autograder.steps.ai_batch_step.AiExecutor") as MockExecutor:
            MockExecutor.return_value.run.return_value = {}
            result_exec = AiBatchStep().execute(pipeline_exec)

        assert result_exec.get_ai_batch_results() == {}

    def test_handles_multiple_ai_tests_in_tree(self):
        class _AiTest2(AiTestFunction):
            @property
            def name(self):
                return "ai_test_2"

            @property
            def description(self):
                return "Second AI test"

            @property
            def parameter_description(self):
                return []

            def build_prompt(self, files, **kwargs):
                return "Second prompt."

        t1 = TestNode(name="ai_1", test_function=_ConcreteAiTest())
        t2 = TestNode(name="ai_2", test_function=_AiTest2())
        base = CategoryNode(name="base", weight=100, tests=[t1, t2])
        tree = CriteriaTree(base=base)

        pipeline_exec = _make_pipeline_exec()
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        with patch("autograder.steps.ai_batch_step.AiExecutor") as MockExecutor:
            MockExecutor.return_value.run.return_value = {}
            AiBatchStep().execute(pipeline_exec)

        call_args = MockExecutor.return_value.run.call_args
        test_inputs = call_args[0][0]  # first positional arg is List[TestInput]
        names = [ti.test_name for ti in test_inputs]
        assert "ai_code_review" in names
        assert "ai_test_2" in names


# ---------------------------------------------------------------------------
# GraderService tests
# ---------------------------------------------------------------------------

class TestGraderServicePreComputedResults:
    """GraderService must thread pre_computed_results through to test functions."""

    def test_pre_computed_results_forwarded_to_test_function(self):
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

            def execute(self, files, sandbox, **kwargs):
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

            def execute(self, files, sandbox, **kwargs):
                return TestResult(test_name="old_style", score=100, report="ok", subject_name="")

        test_node = TestNode(name="old_test", test_function=_TestWithExecutorAttr())
        base = CategoryNode(name="base", weight=100, tests=[test_node])
        tree = CriteriaTree(base=base)

        svc = GraderService()
        # Should complete without calling executor.stop()
        result_tree = svc.grade_from_tree(criteria_tree=tree, submission_files={})

        # The executor.stop() should never have been called
        _TestWithExecutorAttr.executor.stop.assert_not_called()


# ---------------------------------------------------------------------------
# GradeStep integration
# ---------------------------------------------------------------------------

class TestGradeStepPassesAiBatchResults:
    """GradeStep must forward AI_BATCH results to GraderService."""

    def _make_pipeline_with_tree_and_ai_batch(self, pre_computed):
        """Build a minimal pipeline_exec that has BUILD_TREE and AI_BATCH results."""
        tree = _build_criteria_tree_no_ai()  # no AI tests needed for this check
        pipeline_exec = _make_pipeline_exec()

        # Inject required prior steps
        from autograder.models.abstract.template import Template

        class _FakeTemplate(Template):
            @property
            def template_name(self):
                return "fake"

            @property
            def template_description(self):
                return "fake"

            @property
            def requires_sandbox(self):
                return False

            def get_test(self, name):
                return None

        pipeline_exec = _inject_step_result(pipeline_exec, StepName.LOAD_TEMPLATE, _FakeTemplate())
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.AI_BATCH, pre_computed)
        return pipeline_exec

    def test_pre_computed_results_passed_to_grader_service(self):
        pre_computed = {"ai_code_review": TestResult("ai_code_review", 77, "good", "")}
        pipeline_exec = self._make_pipeline_with_tree_and_ai_batch(pre_computed)

        captured = {}

        def _fake_grade_from_tree(**kwargs):
            captured.update(kwargs)
            # Return a minimal ResultTree
            from autograder.models.result_tree import ResultTree, RootResultNode, CategoryResultNode
            cat = CategoryResultNode(name="base", weight=100)
            root = RootResultNode(name="root", base=cat)
            return ResultTree(root)

        with patch.object(GraderService, "grade_from_tree", side_effect=_fake_grade_from_tree):
            GradeStep().execute(pipeline_exec)

        assert captured.get("pre_computed_results") is pre_computed

    def test_pre_computed_results_is_none_when_no_ai_batch_step(self):
        """When AI_BATCH step was not in the pipeline, None must be passed."""
        tree = _build_criteria_tree_no_ai()
        pipeline_exec = _make_pipeline_exec()

        from autograder.models.abstract.template import Template

        class _FakeTemplate(Template):
            @property
            def template_name(self):
                return "fake"

            @property
            def template_description(self):
                return "fake"

            @property
            def requires_sandbox(self):
                return False

            def get_test(self, name):
                return None

        pipeline_exec = _inject_step_result(pipeline_exec, StepName.LOAD_TEMPLATE, _FakeTemplate())
        pipeline_exec = _inject_step_result(pipeline_exec, StepName.BUILD_TREE, tree)

        captured = {}

        def _fake_grade_from_tree(**kwargs):
            captured.update(kwargs)
            from autograder.models.result_tree import ResultTree, RootResultNode, CategoryResultNode
            cat = CategoryResultNode(name="base", weight=100)
            root = RootResultNode(name="root", base=cat)
            return ResultTree(root)

        with patch.object(GraderService, "grade_from_tree", side_effect=_fake_grade_from_tree):
            GradeStep().execute(pipeline_exec)

        assert captured.get("pre_computed_results") is None


# ---------------------------------------------------------------------------
# AiExecutor stateless contract
# ---------------------------------------------------------------------------

class TestAiExecutorStateless:
    """AiExecutor.run() must be stateless: no global singleton, no mutation."""

    def test_run_returns_empty_dict_on_empty_test_list(self):
        from autograder.utils.executors.ai_executor import AiExecutor

        executor = AiExecutor.__new__(AiExecutor)  # skip __init__ (avoids API key lookup)
        # Patch the client attribute so no real API call happens
        executor.client = MagicMock()

        result = executor.run(tests=[], submission_files={})
        assert result == {}
        executor.client.responses.parse.assert_not_called()

    def test_two_instances_are_independent(self):
        """Verify there is no module-level singleton that could bleed state."""
        import autograder.utils.executors.ai_executor as mod

        assert not hasattr(mod, "ai_executor"), (
            "Module-level 'ai_executor' singleton must have been removed."
        )

    def test_outputs_to_results_maps_by_title(self):
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput, TestOutput

        inputs = [TestInput(test_name="t1", prompt="p1"), TestInput(test_name="t2", prompt="p2")]
        outputs = [
            TestOutput(title="t1", feedback="fb1", subject="s1", score=80.0),
            TestOutput(title="t2", feedback="fb2", subject="s2", score=60.0),
        ]

        mapping = AiExecutor._outputs_to_results(inputs, outputs)

        assert "t1" in mapping
        assert mapping["t1"].score == 80.0
        assert mapping["t1"].report == "fb1"
        assert "t2" in mapping
        assert mapping["t2"].score == 60.0

    def test_outputs_to_results_skips_unknown_titles(self):
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput, TestOutput

        inputs = [TestInput(test_name="t1", prompt="p")]
        outputs = [
            TestOutput(title="unknown_test", feedback="fb", subject="s", score=50.0)
        ]

        mapping = AiExecutor._outputs_to_results(inputs, outputs)

        assert "unknown_test" not in mapping
        assert mapping == {}
