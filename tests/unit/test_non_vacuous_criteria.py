"""Compilation rejects criteria whose result cannot depend on the submission (ONB-01).

The catalog test iterates ``describe_templates()``, so every future built-in
evaluator is covered: given only its required parameters it must not score 100
on an irrelevant project, unless it declares itself an absence check (a
prohibition or limit) with a published reason.
"""
# Test names state each checked behaviour.
# pylint: disable=missing-function-docstring
from copy import deepcopy

import pytest

from autograder import DefinitionValidationError, compile_definition, describe_templates, evaluate_submission
from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.definition import compile_snapshot
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.services.definition_migration import convert_legacy_definition
from tests.process_results import exited

#: Relevant file types, irrelevant content (one empty array for array checks).
PROJECT = {"index.html": "<p>hi</p>", "style.css": "p { color: red; }",
           "script.js": "const data = [];\nconsole.log(data);\n"}

CATALOG = [(template.identifier, evaluator)
           for template in describe_templates().templates for evaluator in template.evaluators]


class _NotFound:
    status_code = 404
    text = "Not Found"

    def json(self):
        raise ValueError("not JSON")


class EmptyWorkspace:
    """An execution/server session for a project without the assessed program."""
    fixture_root = "/fixtures"

    def prepare_workdir(self, files):
        del files

    def stage_fixtures(self, fixtures):
        del fixtures

    def run_process(self, request):
        return exited(stderr=f"{request.program[0]}: No such file or directory", code=1)

    def read_artifact(self, path):
        raise FileNotFoundError(path)

    def close(self):
        pass

    def start_server(self):
        pass

    def wait_ready(self):
        pass

    def stop_server(self):
        pass

    def make_request(self, method, endpoint):
        del method, endpoint
        return _NotFound()


HOST = HostCapabilities(execution=lambda language, budget: EmptyWorkspace(),
                        server_execution=lambda language, budget: EmptyWorkspace())


def single(template, evaluator, parameters, language="node"):
    return {"schema_version": "1.0", "templates": [template], "languages": [language],
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": "only", "type": evaluator, "name": "Only", "weight": 100, "parameters": parameters}]}}}


@pytest.mark.parametrize("template,evaluator", CATALOG, ids=[evaluator.identifier for _, evaluator in CATALOG])
def test_required_parameters_alone_never_pass_an_irrelevant_project(template, evaluator):
    reason = getattr(evaluator, "absence_check", None)
    if reason is not None:
        # A prohibition or limit passes when what it forbids is absent; the catalog says why.
        assert reason.strip() and reason == reason.strip()
        return
    if "ai_provider" in evaluator.required_capabilities:
        # The score is the provider's judgement of the submission, never a parameter default.
        return
    required = evaluator.parameters_schema.get("required", [])
    parameters = {name: evaluator.sample_parameters[name] for name in required}
    files = {name: SubmissionFile(name, content) for name, content in PROJECT.items()}
    outcome = evaluate_submission(Submission("s", "s", "a", files),
                                  definition=single(template, evaluator.identifier, parameters), capabilities=HOST)
    assert outcome.status == "completed", outcome.error
    assert outcome.score < 100, (evaluator.identifier, parameters, outcome.tree.base.tests[0].report)


def test_the_reported_header_case_no_longer_passes():
    outcome = evaluate_submission(Submission("s", "s", "a", {"index.html": SubmissionFile("index.html", "<p>hi</p>")}),
                                  definition=single("webdev", "has_tag", {"tag": "header"}))
    assert outcome.score == 0
    assert outcome.tree.base.tests[0].report == "Found 0 of 1 required `<header>` tags."


THRESHOLDS = [
    ("has_tag", {"tag": "header"}, "required_count"),
    ("has_class", {"class_names": ["card"]}, "required_count"),
    ("has_attribute", {"attribute": "alt"}, "required_count"),
    ("check_internal_links", {}, "required_count"),
    ("check_internal_links_to_article", {}, "required_count"),
    ("link_points_to_page_with_query_param", {"target_page": "detail.html", "query_param": "id"}, "required_count"),
    ("js_uses_dom_manipulation", {"methods": ["appendChild"]}, "required_count"),
    ("js_has_json_array_with_id", {"required_key": "id"}, "min_items"),
    ("has_style", {"style": "color"}, "count"),
]


@pytest.mark.parametrize("evaluator,parameters,threshold", THRESHOLDS, ids=[item[0] for item in THRESHOLDS])
def test_presence_thresholds_default_to_one_and_reject_zero(evaluator, parameters, threshold):
    compiled = compile_definition(single("webdev", evaluator, parameters))
    assert compiled.definition.criteria.base.tests[0].parameters[threshold] == 1
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(single("webdev", evaluator, {**parameters, threshold: 0}))
    assert [error["path"] for error in failure.value.errors()] == [
        ["criteria", "base", "tests", 0, "parameters", threshold]]


@pytest.mark.parametrize("evaluator,parameters,field", [
    ("has_class", {}, "class_names"),
    ("has_class", {"class_names": []}, "class_names"),
    ("js_uses_dom_manipulation", {}, "methods"),
    ("js_uses_dom_manipulation", {"methods": []}, "methods"),
])
def test_presence_lists_name_at_least_one_item(evaluator, parameters, field):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(single("webdev", evaluator, parameters))
    assert [error["path"] for error in failure.value.errors()] == [
        ["criteria", "base", "tests", 0, "parameters", field]]


@pytest.mark.parametrize("parameters,code,path", [
    ({}, "INVALID_DEFINITION", ["forbidden_imports"]),
    ({"forbidden_imports": []}, "INVALID_DEFINITION", ["forbidden_imports"]),
    ({"forbidden_imports": [""]}, "INVALID_DEFINITION", ["forbidden_imports", 0]),
])
def test_forbidden_import_names_at_least_one_library(parameters, code, path):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(single("static_analysis", "forbidden_import", parameters, "python"))
    assert [(error["code"], error["path"]) for error in failure.value.errors()] == [
        (code, ["criteria", "base", "tests", 0, "parameters", *path])]


@pytest.mark.parametrize("parameters", [{}, {"forbidden_keywords": [], "custom_ast_grep_rules": []}])
def test_forbidden_keyword_needs_a_keyword_or_a_custom_rule(parameters):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(single("static_analysis", "forbidden_keyword", parameters, "python"))
    assert [(error["code"], error["path"]) for error in failure.value.errors()] == [
        ("EMPTY_FORBIDDEN_LIST", ["criteria", "base", "tests", 0, "parameters", "forbidden_keywords"])]
    compile_definition(single("static_analysis", "forbidden_keyword", {"forbidden_keywords": ["for_loop"]}, "python"))
    compile_definition(single("static_analysis", "forbidden_keyword",
                              {"custom_ast_grep_rules": [{"pattern": "print($$$)"}]}, "python"))


VALID_SNAPSHOT_HASH = "ee992deb7e05ea641bc866aaddddfa8781e67c7d0117dc14381482f35d7a94e3"


def stored_snapshot():
    """A canonical snapshot as stored before ONB-01; it lists every parameter."""
    return {"schema_version": "1.0", "templates": ["webdev", "static_analysis"], "languages": ["node"],
            "criteria": {"base": {"weight": 100.0, "tests": [
                {"id": "tags", "type": "has_tag", "name": "Sections", "parameters": {"tag": "section", "required_count": 2},
                 "file": None, "weight": 1.0, "metadata": {}},
                {"id": "imports", "type": "forbidden_import", "name": "No fs", "parameters": {"forbidden_imports": ["fs"]},
                 "file": None, "weight": 1.0, "metadata": {}}],
                "subjects": None, "subjects_weight": None, "metadata": {}}, "bonus": None, "penalty": None, "metadata": {}},
            "preparation": {"languages": {}, "fixtures": []},
            "feedback": {"enabled": False, "mode": "default", "preferences": {
                "general": {"report_title": None, "show_score": True, "show_passed_tests": False,
                            "add_report_summary": True, "online_content": []},
                "default": {"category_headers": {}}}},
            "metadata": {}}


def test_valid_stored_snapshots_keep_their_meaning_and_hash():
    snapshot = stored_snapshot()
    compiled = compile_snapshot(deepcopy(snapshot))
    assert compiled.definition_hash == VALID_SNAPSHOT_HASH
    assert compiled.definition.model_dump(mode="json") == snapshot
    assert convert_legacy_definition(deepcopy(snapshot)) == snapshot


@pytest.mark.parametrize("mutate,path", [
    (lambda tests: tests[0]["parameters"].update(required_count=0), [0, "parameters", "required_count"]),
    (lambda tests: tests[1]["parameters"].update(forbidden_imports=[]), [1, "parameters", "forbidden_imports"]),
])
def test_now_invalid_stored_snapshots_are_rejected_by_loader_and_converter(mutate, path):
    snapshot = stored_snapshot()
    mutate(snapshot["criteria"]["base"]["tests"])
    expected = ["criteria", "base", "tests", *path]
    with pytest.raises(DefinitionValidationError) as loaded:
        compile_snapshot(deepcopy(snapshot))
    assert [error["path"] for error in loaded.value.errors()] == [expected]
    with pytest.raises(DefinitionValidationError) as converted:
        convert_legacy_definition(snapshot)
    assert [error["path"] for error in converted.value.errors()] == [expected]


def test_legacy_rows_with_a_zero_threshold_are_rejected_for_instructor_correction():
    legacy = {"template_name": "webdev", "languages": ["node"], "grading_criteria": {"base": {"weight": 100, "tests": [
        {"name": "has_tag", "parameters": [{"name": "tag", "value": "header"}, {"name": "required_count", "value": 0}]}]}}}
    with pytest.raises(DefinitionValidationError) as failure:
        convert_legacy_definition(legacy)
    assert [error["path"] for error in failure.value.errors()] == [
        ["criteria", "base", "tests", 0, "parameters", "required_count"]]
    legacy["grading_criteria"]["base"]["tests"][0]["parameters"].pop()
    converted = convert_legacy_definition(legacy)
    assert converted["criteria"]["base"]["tests"][0]["parameters"] == {"tag": "header", "required_count": 1}
