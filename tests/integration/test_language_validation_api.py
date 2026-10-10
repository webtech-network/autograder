"""Definition validation is an HTTP seam and requires no sandbox provisioning."""

import pytest
from tests.web.conftest import db_engine, session_factory, application, test_client  # pylint: disable=unused-import
from tests.web.test_contracts_v1 import definition


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "languages,expected",
    [
        (["python", "java"], 200),
        (["python", "rust"], 422),
        ([], 422),
        (["PYTHON"], 422),
    ],
)
async def test_definition_languages_are_explicit_canonical_values(
    test_client, languages, expected
):
    config = definition()
    config["languages"] = languages
    response = await test_client.post(
        "/api/v1/configs",
        json={"external_assignment_id": "language-validation", "definition": config},
    )
    assert response.status_code == expected, response.text
    if expected == 200:
        assert response.json()["definition"]["languages"] == languages
        assert len(response.json()["definition_hash"]) == 64
    else:
        errors = response.json()["detail"]
        assert errors and all(
            {"code", "path", "message"} <= error.keys() for error in errors
        )
        assert (await test_client.get("/api/v1/configs")).json() == []
