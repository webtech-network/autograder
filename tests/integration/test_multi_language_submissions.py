"""Acceptance selects the requested language while retaining one exact definition."""
import pytest

from tests.web.conftest import db_engine, session_factory, application, test_client  # pylint: disable=unused-import
from tests.web.test_contracts_v1 import definition
from web.database.models.submission import Submission


@pytest.mark.asyncio
async def test_multiple_languages_require_selection_and_bind_same_snapshot(test_client, session_factory):
    """Every accepted language binds the stored snapshot before asynchronous work."""
    config = definition()
    config["languages"] = ["python", "java", "node", "cpp"]
    config["criteria"]["base"]["tests"][0]["parameters"]["program_command"] = {
        "python": "python main.py", "java": "java Main", "node": "node main.js", "cpp": "./main"}
    response = await test_client.post("/api/v1/configs",
        json={"external_assignment_id": "multi", "definition": config})
    assert response.status_code == 200, response.text
    resource = response.json()
    request = {"external_assignment_id": "multi", "external_user_id": "student",
        "username": "Student", "files": [{"filename": "main.py", "content": "print('Hello')"}]}
    missing = await test_client.post("/api/v1/submissions", json=request)
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["code"] == "LANGUAGE_REQUIRED"
    for language in config["languages"]:
        accepted = await test_client.post("/api/v1/submissions", json={**request, "language": language})
        assert accepted.status_code == 202, accepted.text
        assert accepted.json()["language"] == language
        async with session_factory() as session:
            bound = await session.get(Submission, accepted.json()["id"])
            assert bound.language == language
            assert bound.definition_snapshot == resource["definition"]
            assert bound.definition_hash == resource["definition_hash"]
            assert bound.configuration_version == resource["version"]


@pytest.mark.asyncio
async def test_case_insensitive_override_normalizes_before_binding(test_client, session_factory):
    """Language aliases normalize at the host boundary before durable acceptance."""
    config = definition()
    config["languages"] = ["python", "java"]
    response = await test_client.post("/api/v1/configs",
        json={"external_assignment_id": "case", "definition": config})
    assert response.status_code == 200
    accepted = await test_client.post("/api/v1/submissions", json={
        "external_assignment_id": "case", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "Main.java", "content": "class Main {}"}], "language": "JAVA"})
    assert accepted.status_code == 202, accepted.text
    assert accepted.json()["language"] == "java"
    async with session_factory() as session:
        assert (await session.get(Submission, accepted.json()["id"])).language == "java"
