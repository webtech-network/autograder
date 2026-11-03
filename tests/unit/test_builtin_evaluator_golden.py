"""Every migrated built-in static evaluator matches the pre-ARC-03 engine exactly."""
import pytest

from autograder import Submission, SubmissionFile, build_pipeline, compile_snapshot
from autograder.models.language import Language
from tests.builtin_evaluator_cases import DEFINITION, SUBMISSIONS, golden, leaves


@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
def test_static_builtins_reproduce_recorded_scores_and_reports(variant):
    expected = golden()[variant]
    pipeline = build_pipeline(definition=DEFINITION)
    files = {name: SubmissionFile(name, content) for name, content in SUBMISSIONS[variant].items()}
    outcome = pipeline.run(Submission(variant, variant, "golden", files, language=Language.NODE)).outcome
    data = outcome.model_dump(mode="json")
    assert data["status"] == "completed", data["error"]
    assert leaves(data["tree"]) == expected["criteria"]
    assert data["score"] == expected["score"]


def test_golden_cases_cover_every_static_builtin_with_both_outcomes():
    compiled = compile_snapshot(build_pipeline(definition=DEFINITION).compiled.definition.model_dump(mode="json"))
    evaluators = {test.criterion_id: test.test_function.name for test in compiled.criteria_tree.get_all_tests()}
    static = {name for identifier in ("webdev", "static_analysis")
              for name, function in compiled.templates[identifier].get_tests().items()
              if "ai_provider" not in function.required_capabilities}
    assert set(evaluators.values()) == static
    recorded = golden()
    for criterion in evaluators:
        assert recorded["good"]["criteria"][criterion][0] != recorded["bad"]["criteria"][criterion][0], criterion
