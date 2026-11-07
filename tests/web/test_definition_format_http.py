"""Every HTTP route that receives a definition answers a 1.0 one with the converter (ONB-07).

The request body is validated against ``GradingDefinition`` before the route
compiles it, so the documented ``UNSUPPORTED_SCHEMA_VERSION`` error (and not a
literal mismatch plus one error per renamed field) must come from that
validation: for ``/configs/validate``, creating and updating a configuration,
and an external attestation's ``definition_snapshot``.
"""
# pylint: disable=missing-function-docstring
from copy import deepcopy
import json
from pathlib import Path

import pytest

from autograder.models.contracts.definition import CONVERT_COMMAND
from tests.web.test_contracts_v1 import HEADERS, create, external, integration_auth  # pylint: disable=unused-import

CORPUS = json.loads((Path(__file__).resolve().parents[1] / "definition_v1_corpus.json").read_text(encoding="utf-8"))
#: The 1.0 authoring source of the Python I/O example, as a teacher would still send it.
V1 = CORPUS["examples/definitions/python-io.json"]["source"]


def the_conversion_error(response, *path):
    assert response.status_code == 422, response.text
    [error] = response.json()["detail"]
    assert error["code"] == "UNSUPPORTED_SCHEMA_VERSION"
    assert error["path"] == ["body", *path, "schema_version"]
    assert CONVERT_COMMAND in error["message"]


@pytest.mark.asyncio
async def test_validate_names_the_converter(test_client):
    assert V1["schema_version"] == "1.0"
    the_conversion_error(await test_client.post("/api/v1/configs/validate", json=deepcopy(V1)))


@pytest.mark.asyncio
async def test_create_names_the_converter_and_stores_nothing(test_client):
    response = await test_client.post("/api/v1/configs", json={"external_assignment_id": "v1",
                                                               "definition": deepcopy(V1)})
    the_conversion_error(response, "definition")
    assert (await test_client.get("/api/v1/configs")).json() == []


@pytest.mark.asyncio
async def test_update_names_the_converter_and_keeps_the_revision(test_client):
    config = await create(test_client)
    response = await test_client.patch(f'/api/v1/configs/{config["id"]}', headers={"If-Match": '"1"'},
                                       json={"definition": deepcopy(V1)})
    the_conversion_error(response, "definition")
    assert (await test_client.get(f'/api/v1/configs/id/{config["id"]}')).json()["version"] == 1


@pytest.mark.asyncio
async def test_external_attestation_names_the_converter(test_client):
    payload = external(await create(test_client), score=100)
    payload["definition_snapshot"] = deepcopy(V1)
    response = await test_client.post("/api/v1/submissions/external-results", headers=HEADERS, json=payload)
    the_conversion_error(response, "definition_snapshot")
