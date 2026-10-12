from autograder import build_pipeline, compile_definition, Submission
from examples.contracts.custom_evaluator import DEFINITION, TrustedTextTemplate


def test_compiled_definition_retains_injected_template_and_tree():
    template = TrustedTextTemplate()
    compiled = compile_definition(DEFINITION, templates={"trusted_text": template})
    pipeline = build_pipeline(definition=compiled)
    assert pipeline.compiled.templates == [template]
    tree = pipeline.compiled.criteria_tree
    execution = pipeline.run(Submission(
        username="local", user_id="local", assignment_id="local", submission_files={}))
    assert pipeline.compiled.criteria_tree is tree
    assert execution.outcome.status == "completed"
    assert execution.outcome.score == 0
