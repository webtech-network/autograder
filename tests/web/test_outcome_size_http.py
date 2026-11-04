"""Maximal attestations through the real ASGI app and request-limit middleware (COR-06)."""
import json

import pytest

from autograder import compile_definition
from autograder.models.contracts.outcome import MAX_REPORT_BYTES
from autograder.models.contracts.verification import MAX_ATTESTATION_BYTES
from submission_contract import MAX_METADATA_BYTES, MAX_REQUEST_BYTES
from tests.unit.test_outcome_size_bounds import largest, sized_definition, worst_outcome
from tests.web.test_contracts_v1 import HEADERS, integration_auth  # pylint: disable=unused-import

URL = "/api/v1/submissions/external-results"


async def create(client, definition):
    response = await client.post("/api/v1/configs", json={"external_assignment_id": "big", "definition": definition})
    assert response.status_code == 200, response.text[:2000]
    return response.json()


def attestation(config, outcome):
    return {
        "grading_config_id": config["id"],
        "external_user_id": "s" * 255,
        "username": "😀" * 255,
        "language": "python",
        "definition_snapshot": config["definition"],
        "outcome": outcome,
        # The largest accepted audit metadata at maximal JSON escaping.
        "submission_metadata": {"run": "\x01" * (MAX_METADATA_BYTES // 6 - 16)},
    }


async def post(client, payload):
    """``json.dumps`` defaults (ASCII escaping, spaced separators) are the largest encoding."""
    body = json.dumps(payload).encode("utf-8")
    response = await client.post(URL, headers={**HEADERS, "Content-Type": "application/json"}, content=body)
    return response, len(body)


def largest_definition():
    """Most criteria, then the longest definition-authored text the budget allows."""
    count = largest(sized_definition, 5000)
    padding = largest(lambda size: sized_definition(count, size), 4 * 1024 * 1024)
    return sized_definition(count, padding)


def config_outcome(config, compiled):
    outcome = worst_outcome(compiled, reference=str(config["id"])).model_dump(mode="json")
    outcome["provenance"]["revision"] = config["version"]
    return outcome


@pytest.mark.asyncio
async def test_largest_valid_definition_with_every_report_at_maximum_is_accepted(test_client):
    definition = largest_definition()
    compiled = compile_definition(definition)
    config = await create(test_client, definition)
    outcome = config_outcome(config, compiled)
    response, size = await post(test_client, attestation(config, outcome))
    assert response.status_code == 200, response.text[:2000]
    assert 0.95 * MAX_ATTESTATION_BYTES < size <= MAX_REQUEST_BYTES
    details = (await test_client.get(f"/api/v1/submissions/{response.json()['submission_id']}/details")).json()
    tests = details["outcome"]["tree"]["base"]["tests"]
    assert len(tests) == len(compiled.criteria_tree.get_all_tests())
    assert all(test["report"] == "\x01" * MAX_REPORT_BYTES for test in tests)


@pytest.mark.asyncio
async def test_attested_report_above_the_bound_is_rejected_with_a_typed_error(test_client):
    definition = sized_definition(2)
    config = await create(test_client, definition)
    outcome = config_outcome(config, compile_definition(definition))
    outcome["tree"]["base"]["tests"][1]["report"] = "x" * (MAX_REPORT_BYTES + 1)
    response, _ = await post(test_client, attestation(config, outcome))
    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["code"] == "text_too_large"
    assert error["path"][-4:] == ["base", "tests", 1, "report"]


@pytest.mark.asyncio
async def test_attested_outcome_above_its_definition_bound_is_rejected_not_truncated(test_client):
    definition = sized_definition(2)
    compiled = compile_definition(definition)
    config = await create(test_client, definition)
    outcome = config_outcome(config, compiled)
    outcome["tree"]["metadata"] = {"stuffing": "x" * compiled.max_outcome_bytes}
    response, size = await post(test_client, attestation(config, outcome))
    assert size < MAX_REQUEST_BYTES  # the request limit alone would have accepted it
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "OUTCOME_TOO_LARGE"
    assert (await test_client.get("/api/v1/submissions")).json() == []


@pytest.mark.asyncio
async def test_definition_whose_attestation_cannot_fit_is_rejected_at_configuration(test_client):
    count = largest(sized_definition, 5000)
    response = await test_client.post("/api/v1/configs", json={
        "external_assignment_id": "too-big", "definition": sized_definition(count + 1)})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "DEFINITION_TOO_LARGE"
