"""ONB-06: every authoring mistake names the field to change and says how to change it.

A corpus of realistic teacher mistakes (seeded from the Phase 5 probe) is
compiled. Each error must carry the offending field's JSON path, a plain message
without pydantic prefixes and, for unknown identifiers, a suggestion. Error codes
are part of the contract and stay as they were.
"""
# pylint: disable=missing-function-docstring
from copy import deepcopy

import pytest

from autograder import DefinitionValidationError, compile_definition

PYTHON_IO = {
    "schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "sum", "type": "expect_output", "name": "Sum",
         "parameters": {"program_command": "python3 main.py", "inputs": ["1", "2"], "expected_output": "3"}}]}},
    "preparation": {"languages": {"python": {"required_files": ["main.py"]}}},
}
WEB = {
    "schema_version": "1.0", "templates": ["webdev"], "languages": ["node"],
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "header", "type": "has_tag", "name": "Header", "file": "index.html",
         "parameters": {"tag": "header", "required_count": 1}}]}},
}


def mistake(base, change):
    value = deepcopy(base)
    change(value)
    return value


def first_test(value):
    return value["criteria"]["base"]["tests"][0]


# (case id, definition, code, path, words the message must contain)
CORPUS = [
    ("base-weight-not-100", mistake(PYTHON_IO, lambda v: v["criteria"]["base"].update(weight=60)),
     "INVALID_DEFINITION", ["criteria", "base", "weight"], ["base weight must equal 100"]),
    ("preparation-language-not-allowed",
     mistake(PYTHON_IO, lambda v: v["preparation"]["languages"].update(java={"required_files": ["Main.java"]})),
     "INVALID_DEFINITION", ["preparation", "languages", "java"], ["java", "languages"]),
    ("duplicate-template", mistake(PYTHON_IO, lambda v: v.update(templates=["input_output", "input_output"])),
     "INVALID_DEFINITION", ["templates", 1], ["distinct"]),
    ("duplicate-language", mistake(PYTHON_IO, lambda v: v.update(languages=["python", "python"])),
     "INVALID_DEFINITION", ["languages", 1], ["distinct"]),
    ("template-misspelled", mistake(WEB, lambda v: v.update(templates=["web_dev"])),
     "UNKNOWN_TEMPLATE", ["templates", 0], ["web_dev", "did you mean `webdev`"]),
    ("template-unknown", mistake(WEB, lambda v: v.update(templates=["html"])),
     "UNKNOWN_TEMPLATE", ["templates", 0], ["input_output", "static_analysis", "webdev"]),
    ("evaluator-template-not-listed", mistake(WEB, lambda v: v.update(templates=["input_output"])),
     "UNKNOWN_EVALUATOR", ["criteria", "base", "tests", 0, "type"], ["`has_tag`", "template `webdev`", "templates"]),
    ("evaluator-misspelled", mistake(WEB, lambda v: first_test(v).update(type="has_tags")),
     "UNKNOWN_EVALUATOR", ["criteria", "base", "tests", 0, "type"], ["has_tags", "did you mean `has_tag`"]),
    ("parameter-misspelled", mistake(WEB, lambda v: first_test(v)["parameters"].update(tagg="nav")),
     "INVALID_DEFINITION", ["criteria", "base", "tests", 0, "parameters", "tagg"], ["did you mean `tag`"]),
    ("parameter-alias-of-another-evaluator",
     mistake(PYTHON_IO, lambda v: first_test(v).update(type="dont_fail")),
     "INVALID_DEFINITION", ["criteria", "base", "tests", 0, "parameters", "inputs"],
     ["`dont_fail` has no parameter `inputs`", "did you mean `user_input`"]),
    ("parameter-of-another-evaluator",
     mistake(PYTHON_IO, lambda v: first_test(v).update(
         type="dont_fail", parameters={"program_command": "python3 main.py", "expected_output": "3"})),
     "INVALID_DEFINITION", ["criteria", "base", "tests", 0, "parameters", "expected_output"],
     ["`dont_fail` has no parameter `expected_output`", "it accepts:", "program_command"]),
    ("empty-category", mistake(PYTHON_IO, lambda v: v["criteria"].update(bonus={"weight": 10})),
     "INVALID_DEFINITION", ["criteria", "bonus"], ["at least 'tests' or 'subjects'"]),
    ("mixed-group-without-split", mistake(PYTHON_IO, lambda v: v["criteria"]["base"].update(
        subjects=[{"subject_name": "More", "weight": 1, "tests": [{**first_test(v), "id": "more"}]}])),
     "INVALID_DEFINITION", ["criteria", "base"], ["subjects_weight"]),
    ("duplicate-criterion-id", mistake(PYTHON_IO, lambda v: v["criteria"]["base"]["tests"].append(first_test(v))),
     "DUPLICATE_CRITERION_ID", ["criteria", "base", "tests", 1, "id"], ["unique"]),
    ("shell-chain-in-command", mistake(PYTHON_IO, lambda v: first_test(v)["parameters"].update(
        program_command="javac Main.java && java Main")),
     "SHELL_OPERATOR", ["criteria", "base", "tests", 0, "parameters", "program_command"], ["setup_commands"]),
    ("shell-chain-in-setup", mistake(PYTHON_IO, lambda v: v["preparation"]["languages"]["python"].update(
        setup_commands=[{"name": "Build", "command": "pip install x > log"}])),
     "SHELL_OPERATOR", ["preparation", "languages", "python", "setup_commands", 0, "command"], ["shell"]),
    ("vacuous-count", mistake(WEB, lambda v: first_test(v)["parameters"].update(required_count=0)),
     "INVALID_DEFINITION", ["criteria", "base", "tests", 0, "parameters", "required_count"], ["greater than"]),
    ("learning-resource-unknown-id", mistake(PYTHON_IO, lambda v: v.update(feedback={"preferences": {"general": {
        "online_content": [{"url": "https://x", "description": "x", "linked_tests": ["missing"]}]}}})),
     "UNKNOWN_CRITERION_REFERENCE",
     ["feedback", "preferences", "general", "online_content", 0, "linked_tests"], ["criterion IDs"]),
    ("absolute-file-target", mistake(WEB, lambda v: first_test(v).update(file="/index.html")),
     "INVALID_PATH", ["criteria", "base", "tests", 0, "file"], ["relative path"]),
]


def errors_of(value):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    return failure.value.errors()


@pytest.mark.parametrize("value,code,path,words", [case[1:] for case in CORPUS], ids=[case[0] for case in CORPUS])
def test_each_mistake_names_its_field_and_explains_itself(value, code, path, words):
    error = errors_of(value)[0]
    assert (error["code"], error["path"]) == (code, path), error
    for word in words:
        assert word in error["message"], error["message"]


@pytest.mark.parametrize("value", [case[1] for case in CORPUS], ids=[case[0] for case in CORPUS])
def test_messages_carry_no_pydantic_prefixes(value):
    for error in errors_of(value):
        assert not error["message"].startswith(("Value error,", "Assertion failed,")), error


def test_a_template_typo_also_explains_every_criterion_that_uses_it():
    value = mistake(WEB, lambda v: v.update(templates=["web_dev"]))
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    codes = [(error["code"], error["path"]) for error in failure.value.errors()]
    assert codes == [("UNKNOWN_TEMPLATE", ["templates", 0]),
                     ("UNKNOWN_EVALUATOR", ["criteria", "base", "tests", 0, "type"])]
    assert "template `webdev`" in failure.value.errors()[1]["message"]


def test_an_unknown_name_with_no_close_match_suggests_nothing():
    [error] = errors_of(mistake(WEB, lambda v: first_test(v).update(type="zzzz")))
    assert "did you mean" not in error["message"]
    assert error["path"] == ["criteria", "base", "tests", 0, "type"]
