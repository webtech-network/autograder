"""Locally produced and externally attested outcomes pass one structural check (ARC-11).

A configuration is created over HTTP; its stored canonical snapshot grades a
submission through the public pipeline; that exact outcome is then attested
through the external-results endpoint. Every tampered variant is rejected by
the endpoint (422) and by the same core check applied to the local outcome.
"""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from autograder import Submission, SubmissionFile, build_pipeline, compile_snapshot
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.contracts.verification import OutcomeStructureError, verify_outcome_tree
from tests.web.test_contracts_v1 import HEADERS, integration_auth  # pylint: disable=unused-import

LABEL = "Imports / check"


def imports(identity, module, weight=1, **extra):
    return {"id": identity, "type": "forbidden_import", "name": LABEL, "weight": weight,
            "parameters": {"forbidden_imports": [module]}, **extra}


DEFINITION = {
    "schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
    "criteria": {
        "base": {"weight": 100, "subjects_weight": 70, "subjects": [
            {"subject_name": "Group / one", "weight": 1, "tests": [imports("os", "os"), imports("sys", "sys", 3)]},
            {"subject_name": "Group / two", "weight": 0, "subjects": [
                {"subject_name": "Inner", "weight": 1, "tests": [imports("re", "re", file="main.py")]}]},
        ], "tests": [imports("json", "json", 0), imports("csv", "csv", 0)]},
        "bonus": {"weight": 10, "tests": [imports("bonus", "math")]},
        "penalty": {"weight": 20, "tests": [imports("penalty", "subprocess")]},
    },
}


async def local_outcome(client, source="print(1)\n"):
    created = await client.post("/api/v1/configs", json={"external_assignment_id": "verified", "definition": DEFINITION})
    assert created.status_code == 200, created.text
    config = created.json()
    compiled = compile_snapshot(config["definition"])
    pipeline = build_pipeline(definition=compiled, provenance=DefinitionProvenance(
        definition_hash=config["definition_hash"], reference=str(config["id"]), revision=config["version"]))
    outcome = pipeline.run(Submission("student", "student", "verified", {"main.py": SubmissionFile("main.py", source)},
                                      language=compiled.definition.languages[0])).outcome
    assert outcome.status == "completed", outcome.error
    return config, compiled, outcome.model_dump(mode="json")


async def attest(client, config, outcome):
    return await client.post("/api/v1/submissions/external-results", headers=HEADERS, json={
        "grading_config_id": config["id"], "external_user_id": "student", "username": "Student",
        "language": "python", "definition_snapshot": config["definition"], "outcome": outcome})


def leaves(tree):
    one, two = tree["base"]["subjects"]
    return one["tests"], two["subjects"][0]["tests"], tree["base"]["tests"]


def swap_ids(tree):
    one, _, _ = leaves(tree)
    one[0]["id"], one[1]["id"] = one[1]["id"], one[0]["id"]


def swap_evaluator(tree):
    leaves(tree)[0][0]["evaluator"] = "forbidden_keyword"


def change_ratio(tree):
    one, _, _ = leaves(tree)
    one[0]["weight"], one[1]["weight"] = one[1]["weight"], one[0]["weight"]


def move_test(tree):
    one, inner, _ = leaves(tree)
    inner.append(one.pop())


def rename_subject(tree):
    tree["base"]["subjects"][0]["name"] = "Group / renamed"


def change_target(tree):
    leaves(tree)[1][0]["file_target"] = ["other.py"]


def drop_target(tree):
    leaves(tree)[1][0]["file_target"] = None


def change_parameters(tree):
    leaves(tree)[0][0]["parameters"] = {"forbidden_imports": ["socket"]}


def drop_category(tree):
    del tree["bonus"]  # everything passes: the clamped root score is still 100


def change_cap(tree):
    tree["penalty"]["weight"] = 30


STRUCTURAL = [swap_ids, swap_evaluator, change_ratio, move_test, rename_subject, change_target, drop_target,
              change_parameters, drop_category, change_cap]


@pytest.mark.asyncio
async def test_local_outcome_is_accepted_as_an_attestation_unchanged(test_client):
    config, compiled, outcome = await local_outcome(test_client)
    verify_outcome_tree(compiled.criteria_tree, ResultOutcomeTree.model_validate(outcome["tree"]))
    response = await test_client.post("/api/v1/submissions/external-results", headers=HEADERS, json={
        "grading_config_id": config["id"], "external_user_id": "student", "username": "Student",
        "language": "python", "definition_snapshot": config["definition"], "outcome": outcome})
    assert response.status_code == 200, response.text
    details = await test_client.get(f'/api/v1/submissions/{response.json()["submission_id"]}/details', headers=HEADERS)
    assert details.json()["outcome"]["tree"] == outcome["tree"]
    assert leaves(outcome["tree"])[1][0]["file_target"] == ["main.py"]


@pytest.mark.asyncio
async def test_omitted_optional_parameters_remain_valid_wire_data(test_client):
    config, compiled, outcome = await local_outcome(test_client)
    for group in leaves(outcome["tree"]):
        for test in group:
            del test["parameters"]
    verify_outcome_tree(compiled.criteria_tree, ResultOutcomeTree.model_validate(outcome["tree"]))
    assert (await attest(test_client, config, outcome)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", STRUCTURAL, ids=[tamper.__name__ for tamper in STRUCTURAL])
async def test_structural_tampering_fails_locally_and_over_http(test_client, tamper):
    # Every criterion passes, so tampering cannot be caught by score arithmetic alone.
    config, compiled, outcome = await local_outcome(test_client)
    tampered = deepcopy(outcome)
    tamper(tampered["tree"])
    tree = ResultOutcomeTree.model_validate(tampered["tree"])
    with pytest.raises(OutcomeStructureError):
        verify_outcome_tree(compiled.criteria_tree, tree)
    response = await attest(test_client, config, tampered)
    assert response.status_code == 422, response.text
    assert "do not match its definition snapshot" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["leaf", "holder", "root"])
async def test_arithmetic_is_validated_independently_of_the_producer(test_client, field):
    config, _, outcome = await local_outcome(test_client, "import os\nimport subprocess\n")
    # base: 70% "Group / one" (os 25% fails, sys 75% passes) = 52.5, the zero-weight
    # group 0, two all-zero direct tests 15% each = 30 -> 82.5; +10 bonus; -20 penalty.
    assert outcome["score"] == 72.5
    tampered = deepcopy(outcome)
    if field == "leaf":
        leaves(tampered["tree"])[0][0]["score"] = 100
    elif field == "holder":
        tampered["tree"]["base"]["subjects"][0]["score"] = 100
    else:
        tampered["tree"]["score"] = tampered["score"] = 82.5
    with pytest.raises(ValidationError):
        ResultOutcomeTree.model_validate(tampered["tree"])
    assert (await attest(test_client, config, tampered)).status_code == 422
