"""Contract review probes cover accepted input reaching its real evaluator."""
from copy import deepcopy

import pytest

from autograder.autograder import build_pipeline
from autograder.models.contracts.definition import compile_definition, DefinitionValidationError
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.services.definition_migration import convert_legacy_definition
from sandbox_manager.models.sandbox_models import Language


def web_definition():
    return {"schema_version": "1.0", "templates": ["webdev"], "languages": ["node"],
        "criteria": {"base": {"weight": 100, "tests": [{"id": "style-usage",
            "type": "count_unused_css_classes", "name": "Style usage",
            "parameters": {"html_file": "index.html", "css_file": "styles.css"}}]}}}


def run_web(value, css):
    pipeline = build_pipeline(definition=value)
    return pipeline.run(Submission(username="alice", user_id="alice", assignment_id="local",
        language=Language.NODE, submission_files={
            "index.html": SubmissionFile("index.html", '<div class="used">Hi</div>'),
            "styles.css": SubmissionFile("styles.css", css)})).outcome


def test_css_evaluator_reads_the_real_submission_files():
    assert run_web(web_definition(), ".used {color: red}").score == 100
    assert run_web(web_definition(), ".unused {color: red}").score == 0


def test_feedback_learning_links_use_criterion_identity():
    value = web_definition()
    value["feedback"] = {"enabled": True, "preferences": {"general": {"online_content": [
        {"url": "https://example.org/css", "description": "CSS resource", "linked_tests": ["style-usage"]}]}}}
    outcome = run_web(value, ".unused {color: red}")
    assert outcome.feedback.status == "completed"
    assert "CSS resource" in outcome.feedback.content
    assert "https://example.org/css" in outcome.feedback.content


def legacy():
    return {"template_name": "webdev", "languages": ["node"], "grading_criteria": {
        "base": {"weight": 100, "tests": [{"name": "check_project_structure", "parameters": [
            {"name": "expected_structure", "value": "index.html"}]}]}}}


@pytest.mark.parametrize("setup", [
    {"global": {"required_files": ["ignored"]}},
    {"assets": [{"source": "fixture", "target": "/etc/config"}]},
    {"assets": [], "global": {"assets": []}},
    {"node": {"setup_commands": "ls"}},
])
def test_converter_rejects_ignored_and_ambiguous_preparation(setup):
    value = legacy()
    value["setup_config"] = setup
    before = deepcopy(value)
    with pytest.raises(DefinitionValidationError):
        convert_legacy_definition(value)
    assert value == before


@pytest.mark.parametrize("path", ["/etc/output", "../output", "a/../output", "a//output", "."])
def test_artifact_path_rejected_before_execution(path):
    value = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
        "criteria": {"base": {"weight": 100, "tests": [{"id": "artifact", "type": "expect_file_artifact",
            "name": "Output", "parameters": {"program_command": "python3 main.py", "artifact_path": path,
                                                  "expected_content": "ok"}}]}}}
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]["path"][:5] == ["criteria", "base", "tests", 0, "parameters"]
