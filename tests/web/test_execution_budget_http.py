"""The host maximum is enforced at validation and acceptance, and every attempt has a deadline (COR-02)."""
# pylint: disable=missing-function-docstring,redefined-outer-name
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from autograder import compile_definition
from autograder.models.capabilities import ExecutionBudget, HostCapabilities
from execution_host.docker import GRADING_CAPACITY_WAIT_SECONDS
from web.service.worker import AttemptClock


def io_definition(count, languages=("python",), preparation=None):
    return {"schema_version": "1.0", "templates": ["input_output"], "languages": list(languages),
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": f"run{index}", "type": "dont_fail", "name": f"Run {index}",
                 "parameters": {"program_command": "CMD"}} for index in range(count)]}},
            "preparation": preparation or {}}


def static_definition():
    return {"schema_version": "1.0", "templates": ["webdev"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": "tag", "type": "has_tag", "name": "Tag", "file": "index.html", "parameters": {"tag": "main"}}]}}}


#: Two I/O criteria need 2 x 30 + 2 x 2 + 60 = 124 s; three need 156 s.
MAXIMUM = 130


@pytest.fixture
def host_maximum(application):
    application.state.host.capabilities = HostCapabilities(max_session_seconds=MAXIMUM)
    return application.state.host


def problems(response):
    assert response.status_code == 422, response.text
    return response.json()["detail"]


@pytest.mark.asyncio
async def test_validation_and_configuration_refuse_a_definition_the_host_cannot_grant(test_client, host_maximum):
    # pylint: disable=unused-argument
    for response in (await test_client.post("/api/v1/configs/validate", json=io_definition(3)),
                     await test_client.post("/api/v1/configs", json={"external_assignment_id": "too-long",
                                                                     "definition": io_definition(3)})):
        [problem] = problems(response)
        assert problem["code"] == "EXECUTION_BUDGET_EXCEEDED" and problem["path"] == ["languages", "python"]
        assert "156 s" in problem["message"] and "130 s" in problem["message"]
    assert (await test_client.post("/api/v1/configs/validate", json=io_definition(2))).status_code == 200
    assert (await test_client.post("/api/v1/configs/validate", json=static_definition())).status_code == 200


@pytest.mark.asyncio
async def test_only_the_languages_that_exceed_are_named(test_client, host_maximum):  # pylint: disable=unused-argument
    value = io_definition(2, languages=("python", "java"), preparation={"languages": {"java": {
        "setup_commands": [{"name": "compile", "command": "javac Main.java"}]}}})
    [problem] = problems(await test_client.post("/api/v1/configs/validate", json=value))
    assert problem["path"] == ["languages", "java"]


@pytest.mark.asyncio
async def test_an_update_that_exceeds_is_refused_and_the_revision_is_kept(test_client, host_maximum):
    # pylint: disable=unused-argument
    created = await test_client.post("/api/v1/configs", json={"external_assignment_id": "a",
                                                              "definition": io_definition(2)})
    assert created.status_code == 200
    response = await test_client.patch(f'/api/v1/configs/{created.json()["id"]}', headers={"If-Match": '"1"'},
                                       json={"definition": io_definition(3)})
    assert problems(response)[0]["code"] == "EXECUTION_BUDGET_EXCEEDED"
    assert (await test_client.get(f'/api/v1/configs/id/{created.json()["id"]}')).json()["version"] == 1


@pytest.mark.asyncio
async def test_acceptance_refuses_before_queueing_when_the_host_maximum_shrank(test_client, application):
    created = await test_client.post("/api/v1/configs", json={"external_assignment_id": "a",
                                                              "definition": io_definition(3)})
    assert created.status_code == 200  # this host stated no maximum when it was configured
    application.state.host.capabilities = HostCapabilities(max_session_seconds=MAXIMUM)
    response = await test_client.post("/api/v1/submissions", json={
        "external_assignment_id": "a", "external_user_id": "s", "username": "s",
        "files": [{"filename": "main.py", "content": "print(1)"}]})
    assert problems(response)[0]["code"] == "EXECUTION_BUDGET_EXCEEDED"
    assert (await test_client.get("/api/v1/submissions")).json() == []


# ----- the attempt deadline -----------------------------------------------------------

def request(value, language="python"):
    """A claimed attempt carries the canonical snapshot bound at acceptance."""
    snapshot = compile_definition(value).definition.model_dump(mode="json") if "criteria" in value else value
    return SimpleNamespace(definition=snapshot, language=language)


def test_an_execution_attempt_is_clocked_from_its_grant_not_from_the_capacity_wait(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("web.service.worker.monotonic", lambda: now[0])
    clock = AttemptClock(request(io_definition(2)), HostCapabilities(), margin=60)
    session = ExecutionBudget(60.0, 2).session_seconds
    assert clock.remaining() == GRADING_CAPACITY_WAIT_SECONDS + session + 60  # waiting is bounded, not budgeted
    acquire = Mock(return_value="session")
    watched = clock.watch(replace(HostCapabilities(), execution=acquire))
    now[0] += 500  # waited for capacity
    assert watched.execution("python", ExecutionBudget(60.0, 2)) == "session"
    assert clock.remaining() == session + 60


def test_ai_only_and_static_attempts_still_have_a_deadline():
    provider = SimpleNamespace(deadline_seconds=190.0)
    ai = {"schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
          "criteria": {"base": {"weight": 100, "tests": [
              {"id": "sort", "type": "ai_sorting_algorithm", "name": "Sort",
               "parameters": {"algorithm_name": "Merge Sort"}}]}}}
    assert 249 < AttemptClock(request(ai), HostCapabilities(ai=provider), margin=60).remaining() <= 250
    assert 59 < AttemptClock(request(static_definition()), HostCapabilities(), margin=60).remaining() <= 60


def test_an_unreadable_snapshot_gets_the_margin_only():
    assert 9 < AttemptClock(request({"invalid": True}), None, margin=10).remaining() <= 10
