"""On-demand comparison of stored canonical outcomes through the real HTTP app."""
import json
from unittest.mock import patch

import pytest
from sqlalchemy import select

from autograder.models.contracts.definition import compile_definition
from tests.unit.models.test_outcome_comparison import build_outcome
from tests.web.test_contracts_v1 import HEADERS, create, definition, integration_auth  # noqa: F401  # pylint: disable=unused-import  # autouse token
from web.database.models.submission import Submission, SubmissionStatus
from web.database.models.submission_result import PipelineStatus, SubmissionResult
from web.service.outcome_delivery import publish_finalized


def revision_two():
    value = definition()
    value["criteria"]["base"]["tests"][0]["name"] = "Greeting"
    value["criteria"]["base"]["tests"].append({
        "id": "farewell", "type": "expect_output", "name": "Farewell", "weight": 1,
        "parameters": {"program_command": "python main.py", "expected_output": "Bye"}})
    return value


def bound(config, scores, *, failed=False, value=None, execution_id="attested"):
    compiled = compile_definition(value or config["definition"])
    assert compiled.definition_hash == config["definition_hash"]
    return build_outcome(compiled, scores, execution_id=execution_id, failed=failed,
                         reference=str(config["id"]), revision=config["version"]).model_dump(mode="json")


async def attest(client, config, scores, **kwargs):
    payload = {"grading_config_id": config["id"], "external_user_id": "student", "username": "Student",
               "language": "python", "definition_snapshot": config["definition"],
               "outcome": bound(config, scores, **kwargs)}
    response = await client.post("/api/v1/submissions/external-results", headers=HEADERS, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["submission_id"]


async def execute(client, application, config, scores, *, failed=False):
    """Accept source, claim it as a worker, and publish a finalized engine outcome."""
    response = await client.post("/api/v1/submissions", json={
        "external_assignment_id": config["external_assignment_id"], "external_user_id": "student",
        "username": "Student", "files": [{"filename": "main.py", "content": "print('Hello')"}]})
    assert response.status_code == 202, response.text
    host = application.state.host
    request, attempt_id = await host.worker.claim()
    assert request.submission_id == response.json()["id"]
    await publish_finalized(host.sessions, request.submission_id,
                            bound(config, scores, failed=failed, execution_id=f"local-{request.submission_id}"),
                            directory=host.settings.RECEIPT_DIR, attempt_id=attempt_id)
    return request.submission_id


async def update(client, config, value):
    response = await client.patch(f'/api/v1/configs/{config["id"]}', headers={"If-Match": f'"{config["version"]}"'},
                                  json={"definition": value})
    assert response.status_code == 200, response.text
    return response.json()


async def compare(client, head, baseline, headers=HEADERS):
    return await client.get(f"/api/v1/submissions/{head}/comparison",
                            params={"baseline_submission_id": baseline}, headers=headers)


async def stored(application):
    async with application.state.host.sessions() as session:
        results = (await session.execute(select(SubmissionResult).order_by(SubmissionResult.id))).scalars().all()
        rows = (await session.execute(select(Submission).order_by(Submission.id))).scalars().all()
        return json.dumps({"outcomes": [result.outcome for result in results],
                           "rows": [[row.id, row.status.value, str(row.graded_at), row.definition_hash,
                                     row.configuration_version, row.attempt_count] for row in rows]},
                          sort_keys=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("headers,status", [({"Authorization": ""}, 401), ({"Authorization": "Bearer wrong"}, 401), (HEADERS, 200)])
async def test_comparison_requires_integration_token(test_client, headers, status):
    config = await create(test_client)
    first, second = await attest(test_client, config, {"hello": 0}), await attest(test_client, config, {"hello": 100})
    response = await compare(test_client, second, first, headers)
    assert response.status_code == status, response.text


@pytest.mark.asyncio
async def test_same_definition_executed_baseline_and_attested_head(test_client, application):
    config = await create(test_client)
    baseline = await execute(test_client, application, config, {"hello": 0})
    head = await attest(test_client, config, {"hello": 100})
    response = await compare(test_client, head, baseline)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["compatibility"] == "same_definition"
    assert (body["score_delta"], body["improved"]) == (100, True)
    assert body["baseline"]["submission_id"] == baseline and body["baseline"]["source"] == "executed"
    assert body["head"]["submission_id"] == head and body["head"]["source"] == "attested"
    assert body["baseline"]["execution_id"] == f"local-{baseline}" and body["head"]["execution_id"] == "attested"
    for side in ("baseline", "head"):
        assert body[side]["provenance"] == {"schema_version": "1.0", "definition_hash": config["definition_hash"],
                                            "reference": str(config["id"]), "revision": 1}
    assert body["criteria"] == [{
        "criterion_id": "hello", "status": "improved", "baseline_label": "Hello", "head_label": "Hello",
        "baseline_score": 0.0, "head_score": 100.0, "delta": 100.0, "baseline_category": "base",
        "head_category": "base", "baseline_weight": 100.0, "head_weight": 100.0}]
    reverse = (await compare(test_client, baseline, head)).json()
    assert reverse["score_delta"] == -100 and reverse["criteria"][0]["status"] == "regressed"


@pytest.mark.asyncio
async def test_cross_revision_attested_outcomes(test_client):
    config = await create(test_client)
    baseline = await attest(test_client, config, {"hello": 50})
    revised = await update(test_client, config, revision_two())
    assert revised["version"] == 2
    head = await attest(test_client, revised, {"hello": 100, "farewell": 0})
    body = (await compare(test_client, head, baseline)).json()
    assert body["compatibility"] == "cross_revision"
    assert body["score_delta"] is None and body["improved"] is None
    assert "not comparable as a whole" in body["explanation"]
    assert body["changed_definition_sections"] == ["criteria"]
    assert (body["baseline"]["provenance"]["revision"], body["head"]["provenance"]["revision"]) == (1, 2)
    assert body["baseline"]["provenance"]["definition_hash"] != body["head"]["provenance"]["definition_hash"]
    assert [(row["criterion_id"], row["status"], row["delta"]) for row in body["criteria"]] == [
        ("hello", "reweighted", 50.0), ("farewell", "introduced", None)]
    hello = body["criteria"][0]
    assert (hello["baseline_label"], hello["head_label"]) == ("Hello", "Greeting")
    assert (hello["baseline_weight"], hello["head_weight"]) == (100.0, 50.0)
    reverse = (await compare(test_client, baseline, head)).json()
    assert [(row["criterion_id"], row["status"]) for row in reverse["criteria"]] == [
        ("hello", "reweighted"), ("farewell", "removed")]


@pytest.mark.asyncio
async def test_changed_parameters_are_redefined_over_http(test_client):
    config = await create(test_client)
    baseline = await attest(test_client, config, {"hello": 100})
    changed = definition()
    changed["criteria"]["base"]["tests"][0]["parameters"]["expected_output"] = "Hello, World"
    revised = await update(test_client, config, changed)
    head = await attest(test_client, revised, {"hello": 0})
    [row] = (await compare(test_client, head, baseline)).json()["criteria"]
    assert (row["status"], row["baseline_score"], row["head_score"], row["delta"]) == ("redefined", 100.0, 0.0, None)


@pytest.mark.asyncio
async def test_missing_submissions_and_baseline_parameter(test_client):
    config = await create(test_client)
    existing = await attest(test_client, config, {"hello": 0})
    missing_head = await compare(test_client, 999, existing)
    assert missing_head.status_code == 404 and missing_head.json()["detail"] == "Submission not found"
    missing_baseline = await compare(test_client, existing, 999)
    assert missing_baseline.status_code == 404
    assert missing_baseline.json()["detail"] == "Baseline submission not found"
    for params in ({}, {"baseline_submission_id": 0}, {"baseline_submission_id": "x"}):
        response = await test_client.get(f"/api/v1/submissions/{existing}/comparison", params=params, headers=HEADERS)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_different_configuration_is_not_comparable(test_client):
    first, second = await create(test_client, "first"), await create(test_client, "second")
    baseline = await attest(test_client, first, {"hello": 0})
    head = await attest(test_client, second, {"hello": 100})
    response = await compare(test_client, head, baseline)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NOT_COMPARABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_side", ["baseline", "head"])
async def test_failed_outcomes_are_not_compared(test_client, application, failed_side):
    config = await create(test_client)
    good = await attest(test_client, config, {"hello": 100})
    bad = await execute(test_client, application, config, {}, failed=True)
    head, baseline = (good, bad) if failed_side == "baseline" else (bad, good)
    response = await compare(test_client, head, baseline)
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "OUTCOME_NOT_COMPLETED", "side": failed_side, "submission_id": bad,
        "message": f"The {failed_side} submission failed and has no authoritative grade"}


@pytest.mark.asyncio
async def test_pending_submission_is_not_completed(test_client):
    config = await create(test_client)
    good = await attest(test_client, config, {"hello": 100})
    pending = await test_client.post("/api/v1/submissions", json={
        "external_assignment_id": "assignment", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "main.py", "content": "print('Hello')"}]})
    response = await compare(test_client, pending.json()["id"], good)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OUTCOME_NOT_COMPLETED"


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", ["no_snapshot", "no_outcome"])
async def test_legacy_unverified_history_is_never_guessed(test_client, application, legacy):
    config = await create(test_client)
    good = await attest(test_client, config, {"hello": 100})
    async with application.state.host.sessions() as session:
        snapshot = legacy == "no_outcome"
        row = Submission(grading_config_id=config["id"], external_user_id="student", username="Student",
                         submission_files={"main.py": "print('Hello')"}, language="python",
                         status=SubmissionStatus.COMPLETED,
                         definition_snapshot=config["definition"] if snapshot else None,
                         definition_hash=config["definition_hash"] if snapshot else None,
                         configuration_version=1 if snapshot else None)
        session.add(row)
        await session.flush()
        # Legacy results had display-path trees and vectors, but no canonical outcome.
        session.add(SubmissionResult(submission_id=row.id, final_score=80, outcome=None,
                                     result_tree={"root": {"children": [{"name": "Hello", "score": 80}]}},
                                     score_vector={"base/Hello": 80}, execution_time_ms=1,
                                     pipeline_status=PipelineStatus.SUCCESS))
        await session.commit()
        legacy_id = row.id
    for head, baseline, side in ((good, legacy_id, "baseline"), (legacy_id, good, "head")):
        response = await compare(test_client, head, baseline)
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert (detail["code"], detail["side"], detail["submission_id"]) == ("LEGACY_UNVERIFIED", side, legacy_id)


@pytest.mark.asyncio
async def test_comparison_never_grades_or_mutates_stored_outcomes(test_client, application):
    config = await create(test_client)
    baseline = await execute(test_client, application, config, {"hello": 0})
    revised = await update(test_client, config, revision_two())
    head = await attest(test_client, revised, {"hello": 100, "farewell": 100})
    before = await stored(application)
    poll_before = (await test_client.get(f"/api/v1/submissions/{head}")).json()
    failing = AssertionError("comparison must not grade")
    with patch("web.service.grading_service.build_pipeline", side_effect=failing), \
            patch("web.service.grading_service._run_pipeline", side_effect=failing), \
            patch("autograder.autograder.AutograderPipeline.run", side_effect=failing), \
            patch("autograder.template_library.input_output.ExpectOutputTest.execute", side_effect=failing):
        responses = [await compare(test_client, head, baseline) for _ in range(3)]
    assert all(response.status_code == 200 for response in responses)
    assert len({response.content for response in responses}) == 1
    assert await stored(application) == before
    poll_after = (await test_client.get(f"/api/v1/submissions/{head}")).json()
    assert poll_after == poll_before and poll_after["comparison_status"] == "disabled"
    async with application.state.host.sessions() as session:
        assert (await session.get(Submission, head)).status == SubmissionStatus.COMPLETED


@pytest.mark.asyncio
async def test_self_comparison_is_unchanged(test_client):
    config = await create(test_client)
    identity = await attest(test_client, config, {"hello": 40})
    body = (await compare(test_client, identity, identity)).json()
    assert (body["compatibility"], body["score_delta"], body["improved"]) == ("same_definition", 0, False)
    assert body["criteria"][0]["status"] == "unchanged"


def test_openapi_documents_authenticated_comparison():
    from web.main import app
    operation = app.openapi()["paths"]["/api/v1/submissions/{submission_id}/comparison"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SubmissionComparisonResponse")
    assert [parameter["name"] for parameter in operation["parameters"]] == ["submission_id", "baseline_submission_id"]
    assert operation["security"] == [{"IntegrationBearer": []}]
