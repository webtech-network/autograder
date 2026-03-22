from autograder.models.criteria_tree import CategoryNode, CriteriaTree
from autograder.models.dataclass.focus import Focus
from autograder.models.dataclass.grade_step_result import GradeStepResult
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.result_tree import CategoryResultNode, ResultTree, RootResultNode
from autograder.template_library.input_output import InputOutputTemplate


def _build_pipeline_execution() -> PipelineExecution:
    submission = Submission(
        username="student",
        user_id=1,
        assignment_id=7,
        submission_files={"main.py": SubmissionFile(filename="main.py", content="print('ok')")},
    )
    return PipelineExecution.start_execution(submission)


def test_typed_accessors_return_expected_artifacts():
    pipeline_exec = _build_pipeline_execution()

    template = InputOutputTemplate()
    tree = CriteriaTree(base=CategoryNode(name="base", weight=100))
    result_tree = ResultTree(root=RootResultNode(base=CategoryResultNode(name="base", weight=100)))
    result_tree.root.base.score = 100.0
    result_tree.root.score = 100.0
    grade = GradeStepResult(final_score=100.0, result_tree=result_tree)
    focus = Focus(base=[], penalty=[], bonus=[])

    pipeline_exec.add_step_result(StepResult(step=StepName.LOAD_TEMPLATE, data=template, status=StepStatus.SUCCESS))
    pipeline_exec.add_step_result(StepResult(step=StepName.BUILD_TREE, data=tree, status=StepStatus.SUCCESS))
    pipeline_exec.add_step_result(StepResult(step=StepName.GRADE, data=grade, status=StepStatus.SUCCESS))
    pipeline_exec.add_step_result(StepResult(step=StepName.FOCUS, data=focus, status=StepStatus.SUCCESS))
    pipeline_exec.add_step_result(StepResult(step=StepName.FEEDBACK, data="ok", status=StepStatus.SUCCESS))

    assert pipeline_exec.get_loaded_template() is template
    assert pipeline_exec.get_built_criteria_tree() is tree
    assert pipeline_exec.get_grade_step_result() is grade
    assert pipeline_exec.get_result_tree() is result_tree
    assert pipeline_exec.require_focus() is focus
    assert pipeline_exec.get_focus() is focus
    assert pipeline_exec.get_feedback() == "ok"
    assert pipeline_exec.get_sandbox() is None


def test_typed_accessors_raise_on_missing_required_artifacts():
    pipeline_exec = _build_pipeline_execution()

    try:
        pipeline_exec.get_loaded_template()
        assert False, "Expected ValueError for missing template step"
    except ValueError as exc:
        assert "template" in str(exc).lower()

    pipeline_exec.add_step_result(
        StepResult(step=StepName.LOAD_TEMPLATE, data=None, status=StepStatus.FAIL, error="boom")
    )
    try:
        pipeline_exec.get_loaded_template()
        assert False, "Expected ValueError for missing template data"
    except ValueError as exc:
        assert "required" in str(exc).lower()
