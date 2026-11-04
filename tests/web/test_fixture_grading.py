"""HTTP grading with assignment fixtures from a host-composed object store (#390)."""
# pylint: disable=missing-function-docstring
import asyncio

import pytest

from autograder.models.capabilities import HostCapabilities
from tests.process_results import exited
from tests.fake_object_store import fake_s3_provider

HEADERS = {"Authorization": "Bearer fixture-token"}


class RecordingSession:
    """A host session that keeps staged bytes and modes as a sandbox would."""
    fixture_root = "/tmp/app"

    def __init__(self, sessions):
        self.files, self.staged, self.commands, self.closed = {}, {}, [], 0
        sessions.append(self)

    def prepare_workdir(self, files):
        self.files = dict(files)

    def stage_fixture(self, path, content, read_only):
        self.staged[path] = (content, read_only)

    def run_process(self, request):
        self.commands.append(" ".join(request.program))
        return exited("ok")

    def close(self):
        self.closed += 1


def fixture_definition(*fixtures):
    return {"schema_version": "1.0", "templates": ["webdev"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [{"id": "entry", "name": "Entry point",
                "type": "check_project_structure", "parameters": {"expected_structure": "main.py"}}]}},
            "preparation": {"languages": {"python": {"setup_commands": [
                {"name": "inspect", "command": "ls -la /tmp/app"}]}},
                "fixtures": [{"reference": reference, "path": path, "read_only": read_only}
                             for reference, path, read_only in fixtures]}}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "fixture-token")


@pytest.fixture
def store(application):
    provider, client = fake_s3_provider({"course/a/b": b"slash", "course/a_b": b"underscore",
                                         "course/empty": b""})
    sessions = []
    application.state.host.capabilities = HostCapabilities(
        execution=lambda language: RecordingSession(sessions), fixtures=provider)
    application.state.host.worker.capabilities = application.state.host.capabilities
    return client, sessions


async def grade(client, application, assignment, definition):
    created = await client.post("/api/v1/configs", json={
        "external_assignment_id": assignment, "definition": definition})
    assert created.status_code in (200, 201), created.text
    submitted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": assignment, "external_user_id": "student-1", "username": "Student",
        "files": [{"filename": "main.py", "content": "print('ok')"}]})
    assert submitted.status_code == 202, submitted.text
    for _ in range(100):
        if await application.state.host.worker.run_once():
            break
        await asyncio.sleep(0.02)
    polled = (await client.get(submitted.headers["Location"])).json()
    details = await client.get(f'/api/v1/submissions/{polled["id"]}/details', headers=HEADERS)
    assert details.status_code == 200, details.text
    return polled, details.json()["outcome"]


@pytest.mark.asyncio
async def test_colliding_and_empty_fixtures_are_staged_exactly_and_graded(client, application, store):
    object_store, sessions = store
    polled, outcome = await grade(client, application, "fixtures-ok", fixture_definition(
        ("course/a_b", "under.txt", False), ("course/a/b", "slash.txt", True),
        ("course/empty", "empty.txt", True)))
    assert polled["status"] == "completed" and polled["final_score"] == 100
    assert outcome["status"] == "completed" and outcome["error"] is None
    [session] = sessions
    assert session.staged == {"under.txt": (b"underscore", False), "slash.txt": (b"slash", True),
                              "empty.txt": (b"", True)}
    assert session.commands == ["ls -la /tmp/app"] and session.closed == 1
    assert [key for _, key in object_store.requests] == ["course/a_b", "course/a/b", "course/empty"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unreachable, retryable", [(False, False), (True, True)])
async def test_missing_or_failed_fixture_yields_safe_preparation_failure(
        client, application, store, unreachable, retryable):
    object_store, sessions = store
    object_store.unreachable = unreachable
    polled, outcome = await grade(client, application, f"fixtures-fail-{unreachable}", fixture_definition(
        ("course/a/b", "slash.txt", True), ("course/not-uploaded", "data.csv", True)))
    assert polled["status"] == "failed" and polled["final_score"] is None
    assert outcome["score"] is None and outcome["tree"] is None
    error = outcome["error"]
    assert (error["category"], error["code"], error["retryable"]) == ("capability", "PREPARATION_ERROR", retryable)
    assert error["message"] == "Assignment preparation could not complete."
    assert "not-uploaded" not in str(polled) and "not-uploaded" not in str(outcome)
    [session] = sessions
    assert session.commands == [] and session.closed == 1
