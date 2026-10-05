from autograder import build_pipeline, compile_definition, Submission
from autograder.models.dataclass.step_result import StepName
from examples.contracts.custom_evaluator import DEFINITION, TrustedTextTemplate


def test_loader_retains_injected_instance_after_recompiling():
    template = TrustedTextTemplate()
    compiled = compile_definition(DEFINITION, templates={"trusted_text": template})
    execution = build_pipeline(definition=compiled).run(Submission(
        username="local", user_id="local", assignment_id="local", submission_files={}))
    assert execution.get_loaded_templates() == [template]
    assert execution.outcome.status == "completed"
    assert execution.outcome.score == 0
    assert StepName.SANDBOX not in execution.planned_steps
    assert StepName.AI_BATCH not in execution.planned_steps
