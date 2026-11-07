"""A host without a runtime profile reports a capability failure over real HTTP (ARC-05).

The definition allows ``python`` and ``c``; the Docker host is configured with a
Python runtime only. ``c`` stays a valid, allowed language: grading fails with
``CAPABILITY_UNAVAILABLE`` and deliberate execution with 503, while Python runs in
a real container. An unknown identifier is still rejected as invalid input.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from autograder.models.language import Language
from execution_host.docker import DockerHost
from tests.sandbox_profiles import sandbox_config
from tests.web.conftest import db_engine, session_factory  # pylint: disable=unused-import
from web.core.config import Settings
from web.main import create_app

HEADERS = {"Authorization": "Bearer profile-token"}
DEFINITION = {
    "schema_version": "2.0", "languages": ["python", "c"],
    "criteria": {"base": {"tests": [
        {"id": "runs", "type": "dont_fail", "name": "Runs", "parameters": {"program_command": "CMD"}}]}},
}


@pytest.fixture
async def python_only_application(session_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "profile-token")
    config = tmp_path / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,)))
    owner = DockerHost(mode="local", config_file=str(config))
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts")), session_factory=session_factory,
                     capabilities=owner.capabilities, resource_owner=owner, start_workers=False)
    await app.state.host.start()
    yield app
    await app.state.host.close()


async def submit(client, app, language, filename, content):
    accepted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": "profiles", "external_user_id": language, "username": language,
        "language": language, "files": [{"filename": filename, "content": content}]})
    if accepted.status_code != 202:
        return accepted.status_code, accepted.json()
    assert await app.state.host.worker.run_once()
    details = await client.get(f"{accepted.headers['Location']}/details")
    return details.status_code, details.json()


@pytest.mark.asyncio
async def test_missing_runtime_is_a_capability_failure_over_http(python_only_application):
    app = python_only_application
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS) as client:
        created = await client.post("/api/v1/configs", json={"external_assignment_id": "profiles", "definition": DEFINITION})
        assert created.status_code == 200, created.text

        status, missing = await submit(client, app, "c", "main.c", "int main(void) { return 0; }\n")
        assert status == 200
        assert missing["status"] == "failed" and missing["language"] == "c"
        assert missing["outcome"]["error"]["code"] == "CAPABILITY_UNAVAILABLE"
        assert missing["outcome"]["error"]["category"] == "capability"
        assert missing["final_score"] is None and missing["outcome"]["tree"] is None

        status, graded = await submit(client, app, "python", "main.py", "print('ok')\n")
        assert graded["status"] == "completed", graded
        assert graded["final_score"] == 100 and graded["language"] == "python"

        status, invalid = await submit(client, app, "rust", "main.rs", "fn main() {}\n")
        assert status == 422  # unknown identifiers are invalid input, not a capability gap

        status, disallowed = await submit(client, app, "java", "Main.java", "class Main {}\n")
        assert status == 422 and disallowed["detail"][0]["code"] == "LANGUAGE_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_deliberate_execution_reports_missing_runtime_as_unavailable(python_only_application):
    async with AsyncClient(transport=ASGITransport(app=python_only_application), base_url="http://test",
                           headers=HEADERS) as client:
        missing = await client.post("/api/v1/execute", json={
            "language": "c", "program_command": "./a.out",
            "submission_files": [{"filename": "main.c", "content": "int main(void) { return 0; }"}]})
        assert missing.status_code == 503 and missing.json()["detail"]["code"] == "EXECUTION_UNAVAILABLE"
        invalid = await client.post("/api/v1/execute", json={
            "language": "rust", "program_command": "true",
            "submission_files": [{"filename": "main.rs", "content": ""}]})
        assert invalid.status_code == 422
        ran = await client.post("/api/v1/execute", json={
            "language": "python", "program_command": "python3 main.py",
            "submission_files": [{"filename": "main.py", "content": "print('ran')"}]})
        assert ran.status_code == 200 and ran.json()["results"][0]["stdout"] == "ran\n"
