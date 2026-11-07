"""Definition format 2.0: no ceremony, one name per idea, one offline conversion (ONB-07).

``tests/definition_v1_corpus.json`` was recorded on the 1.0 engine (refactor/363
at 0e357ad7) from every checked-in definition: its raw authoring input, and for
a valid one the canonical snapshot, its hash and each criterion's category,
final-score points and evaluator as 1.0 computed them. The converter must
reproduce every one of them in format 2.0.
"""
# pylint: disable=missing-function-docstring
from copy import deepcopy
import json
from pathlib import Path

import pytest

from autograder import (
    DefinitionValidationError, Submission, SubmissionFile, build_pipeline, compile_definition, compile_snapshot,
)
from autograder import Template, TestFunction, TestResult
from autograder.models.contracts.comparison import _definition_criteria
from autograder.models.contracts.definition import snapshot_hash
from autograder.models.language import Language
from autograder.services.definition_migration import (
    RENAMED_EVALUATORS, convert_definition, convert_snapshot, main, upgrade_v1,
)
from tests.builtin_evaluator_cases import SUBMISSIONS, golden, leaves

ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((ROOT / "tests/definition_v1_corpus.json").read_text(encoding="utf-8"))
VALID = sorted(name for name, entry in CORPUS.items() if "snapshot" in entry)
INVALID = sorted(name for name, entry in CORPUS.items() if "errors" in entry)
#: 1.0 errors that 2.0 makes impossible: the field they were about no longer exists.
REMOVED_MISTAKES = {"examples/definitions/invalid/misspelled-template.json",
                    "examples/definitions/invalid/base-weight-not-100.json"}

MINIMAL = {"schema_version": "2.0", "languages": ["python"], "criteria": {"base": {"tests": [
    {"id": "sum", "type": "expect_output", "name": "Sum",
     "parameters": {"program_command": "python3 main.py", "inputs": ["1", "2"], "expected_output": "3"}},
    {"id": "no-os", "type": "forbidden_import", "name": "No os", "parameters": {"forbidden_imports": ["os"]}},
]}}}


def scoring(definition):
    """Criterion ID -> [category, final-score points, evaluator], as recorded in the corpus."""
    from autograder.models.contracts.definition import GradingDefinition
    model = GradingDefinition.model_validate(definition)
    return {test.id: [category, round(points, 9), test.type] for test, category, points in _definition_criteria(model)}


# --- The authoring shape -------------------------------------------------------------

def test_a_minimal_definition_names_no_templates_and_no_base_weight():
    compiled = compile_definition(deepcopy(MINIMAL))
    snapshot = compiled.definition.model_dump(mode="json")
    assert "templates" not in snapshot and "weight" not in snapshot["criteria"]["base"]
    # Evaluators from two built-in templates, each resolved by `type` alone.
    assert [test.test_function.name for test in compiled.criteria_tree.get_all_tests()] == [
        "expect_output", "forbidden_import"]
    assert compiled.criteria_tree.base.weight == 100


def test_groups_and_criteria_share_one_label_and_one_weight_rule():
    value = deepcopy(MINIMAL)
    tests = value["criteria"]["base"].pop("tests")
    value["criteria"]["base"]["subjects"] = [{"name": "Output", "weight": 250, "tests": tests[:1]},
                                             {"name": "Rules", "tests": tests[1:]}]
    value["criteria"]["penalty"] = {"max_points": 30, "tests": [{**tests[1], "id": "again", "weight": 1000}]}
    compiled = compile_definition(value)
    subjects = compiled.criteria_tree.base.subjects
    assert [(subject.name, round(subject.weight, 6)) for subject in subjects] == [("Output", 71.428571),
                                                                                    ("Rules", 28.571429)]
    assert compiled.criteria_tree.penalty.weight == 30
    for bad in (-1, True, "1", float("inf")):
        broken = deepcopy(value)
        broken["criteria"]["base"]["subjects"][0]["weight"] = bad
        with pytest.raises(DefinitionValidationError):
            compile_definition(broken)


def test_a_1_0_definition_is_rejected_with_the_conversion_command():
    for compile_ in (compile_definition, compile_snapshot):
        with pytest.raises(DefinitionValidationError) as failure:
            compile_(deepcopy(CORPUS["examples/definitions/python-io.json"]["snapshot"]))
        [error] = failure.value.errors()
        assert (error["code"], error["path"]) == ("UNSUPPORTED_SCHEMA_VERSION", ["schema_version"])
        assert "python -m autograder.services.definition_migration" in error["message"]


class _Named(TestFunction):
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "A trusted local check."

    def execute(self, evaluation):
        return TestResult(self._name, 100, "ok")


def test_injected_templates_join_resolution_and_collisions_are_compile_errors():
    local = Template("Local", "Trusted local checks", [_Named("has_tag"), _Named("local_check")])
    value = deepcopy(MINIMAL)
    value["criteria"]["base"]["tests"].append({"id": "local", "type": "local_check", "name": "Local",
                                                "parameters": {}})
    # An unused colliding identifier is harmless; the injected evaluator resolves by type.
    compiled = compile_definition(value, templates={"local": local})
    assert compiled.criteria_tree.base.tests[-1].test_function.name == "local_check"
    value["criteria"]["base"]["tests"].append({"id": "tag", "type": "has_tag", "name": "Tag", "parameters": {}})
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value, templates={"local": local})
    [error] = failure.value.errors()
    assert (error["code"], error["path"]) == ("AMBIGUOUS_EVALUATOR", ["criteria", "base", "tests", 3, "type"])
    assert "local, webdev" in error["message"]
    # Injecting under a built-in identifier replaces that template: nothing is ambiguous.
    assert compile_definition(value, templates={"webdev": local}).criteria_tree.base.tests[-1].test_function.name \
        == "has_tag"


# --- The converter ---------------------------------------------------------------------

@pytest.mark.parametrize("name", VALID)
def test_every_recorded_1_0_definition_converts_with_identical_scoring(name):
    entry = CORPUS[name]
    from_source = convert_definition(deepcopy(entry["source"]))
    from_snapshot = convert_snapshot(deepcopy(entry["snapshot"]))
    assert from_source.definition == from_snapshot.definition
    assert from_source == convert_definition(deepcopy(entry["source"]))  # deterministic
    assert convert_definition(from_source.definition) == (from_source.definition, [])  # 2.0 is only checked
    renamed = {identity: [category, points, RENAMED_EVALUATORS.get(evaluator, evaluator)]
               for identity, (category, points, evaluator) in entry["criteria"].items()}
    assert scoring(from_snapshot.definition) == renamed
    # The stored 1.0 snapshot still verifies against the hash recorded with it.
    assert snapshot_hash(entry["snapshot"]) == entry["definition_hash"]


@pytest.mark.parametrize("name", INVALID)
def test_every_recorded_1_0_rejection_is_still_reported_or_is_gone_with_its_field(name):
    entry = CORPUS[name]
    if name in REMOVED_MISTAKES:
        if "base-weight" in name:  # a base weight other than 100 was never valid: reported, not guessed
            with pytest.raises(DefinitionValidationError) as failure:
                convert_definition(deepcopy(entry["source"]))
            assert failure.value.errors()[0]["path"] == ["criteria", "base", "weight"]
        else:  # the misspelled template list is simply gone
            convert_definition(deepcopy(entry["source"]))
        return
    with pytest.raises(DefinitionValidationError) as failure:
        convert_definition(deepcopy(entry["source"]))
    assert sorted({error["code"] for error in failure.value.errors()}) == entry["errors"]


@pytest.mark.parametrize("path", sorted(name for name in CORPUS if name.endswith(".json")))
def test_each_checked_in_definition_is_the_conversion_of_its_recorded_1_0_source(path):
    if path.split("/")[-1] in ("misspelled-template.json", "base-weight-not-100.json"):
        assert not (ROOT / path).exists()  # replaced by removed-base-weight.json and misspelled-evaluator.json
        return
    checked_in = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert checked_in == upgrade_v1(CORPUS[path]["source"]).definition


@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
def test_converted_builtin_rubric_reproduces_the_recorded_scores_and_reports(variant):
    converted = convert_definition(CORPUS["tests/builtin_evaluator_cases.py:DEFINITION"]["source"])
    files = {name: SubmissionFile(name, content) for name, content in SUBMISSIONS[variant].items()}
    outcome = build_pipeline(definition=converted.definition).run(
        Submission(variant, variant, "golden", files, language=Language.NODE)).outcome.model_dump(mode="json")
    assert leaves(outcome["tree"]) == golden()[variant]["criteria"]
    assert outcome["score"] == golden()[variant]["score"]
    assert [note["path"][-2] for note in converted.notes] == [34, 35]  # the two multi-file web checks


def test_each_mapping_and_what_the_converter_refuses():
    def v1(*tests, **criteria):
        return {"schema_version": "1.0", "templates": ["input_output", "webdev"], "languages": ["python"],
                "criteria": {"base": {"weight": 100, "tests": list(tests)}, **criteria}}

    run = {"program_command": "python3 main.py"}
    source = v1({"id": "a", "type": "dont_fail", "name": "A", "parameters": {**run, "user_input": "4"}},
                {"id": "b", "type": "dont_fail", "name": "B", "parameters": {**run, "user_input": ""}},
                {"id": "c", "type": "has_style", "name": "C", "parameters": {"style": "margin", "count": 2}},
                {"id": "d", "type": "check_bootstrap_usage", "name": "D", "parameters": {}},
                bonus={"weight": 10, "subjects": [{"subject_name": "S", "weight": 1, "tests": [
                    {"id": "e", "type": "count_unused_css_classes", "name": "E",
                     "parameters": {"html_file": "index.html", "css_file": "style.css"}}]}]})
    result = convert_definition(source)
    tests = result.definition["criteria"]["base"]["tests"]
    assert [test["parameters"].get("inputs") for test in tests[:2]] == [["4"], []]  # the same stdin bytes
    assert tests[2]["parameters"] == {"style": "margin", "required_count": 2}
    assert tests[3]["type"] == "has_no_bootstrap"
    bonus = result.definition["criteria"]["bonus"]
    assert bonus["max_points"] == 10 and bonus["subjects"][0]["name"] == "S"
    assert bonus["subjects"][0]["tests"][0]["parameters"] == {}
    [note] = result.notes
    assert note["path"] == ["criteria", "bonus", "subjects", 0, "tests", 0, "parameters"]
    assert "every HTML and CSS file" in note["message"]
    refused = {
        "competing stdin": (lambda value: value["criteria"]["base"]["tests"][0]["parameters"].update(inputs=["4"]),
                            ["criteria", "base", "tests", 0, "parameters", "user_input"]),
        "non-string stdin": (lambda value: value["criteria"]["base"]["tests"][0]["parameters"].update(user_input=4),
                             ["criteria", "base", "tests", 0, "parameters", "user_input"]),
        "base weight": (lambda value: value["criteria"]["base"].update(weight=60), ["criteria", "base", "weight"]),
        "competing cap": (lambda value: value["criteria"]["bonus"].update(max_points=10),
                          ["criteria", "bonus", "weight"]),
    }
    for change, path in refused.values():
        value = deepcopy(source)
        change(value)
        with pytest.raises(DefinitionValidationError) as failure:
            convert_definition(value)
        assert [(error["code"], error["path"]) for error in failure.value.errors()] == [("CONVERSION_REJECTED", path)]


def test_the_command_writes_the_definition_and_reports_notes_and_errors(tmp_path, capsys):
    source, destination = tmp_path / "old.json", tmp_path / "definition.json"
    source.write_text(json.dumps(CORPUS["tests/builtin_evaluator_cases.py:DEFINITION"]["source"]), encoding="utf-8")
    main([str(source), str(destination)])
    assert json.loads(destination.read_text(encoding="utf-8"))["schema_version"] == "2.0"
    assert len(json.loads(capsys.readouterr().err)["notes"]) == 2
    source.write_text(json.dumps(CORPUS["examples/definitions/invalid/zero-presence-threshold.json"]["source"]))
    with pytest.raises(SystemExit) as exit_:
        main([str(source), str(destination)])
    assert exit_.value.code == 2
    assert json.loads(capsys.readouterr().out)["errors"][0]["path"][-1] == "required_count"


def test_the_real_container_golden_rubric_is_the_conversion_of_its_recorded_1_0_form():
    """``test_canonical_outcome_golden`` grades this 2.0 rubric in Docker against the outcome recorded on 1.0."""
    from tests.integration.test_canonical_outcome_golden import DEFINITION
    recorded = CORPUS["tests/integration/test_canonical_outcome_golden.py:DEFINITION"]["source"]
    assert convert_definition(recorded).definition == compile_definition(DEFINITION).definition.model_dump(mode="json")
