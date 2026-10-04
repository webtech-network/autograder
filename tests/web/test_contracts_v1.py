"""Contract seams use real registry validation and isolated SQL persistence."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch
import pytest
from autograder.models.contracts.definition import compile_definition
from web.config import auth


def definition():
    return {
        "schema_version": "1.0",
        "templates": ["input_output"],
        "languages": ["python"],
        "criteria": {
            "base": {
                "weight": 100,
                "tests": [
                    {
                        "id": "hello",
                        "type": "expect_output",
                        "name": "Hello",
                        "weight": 1,
                        "parameters": {
                            "program_command": "python main.py",
                            "expected_output": "Hello",
                        },
                    }
                ],
            }
        },
    }


@pytest.fixture(autouse=True)
def integration_auth(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "test-contract-token")
    monkeypatch.setattr(auth, "integration_auth_config", None)


HEADERS = {"Authorization": "Bearer test-contract-token"}


async def create(client, assignment="assignment"):
    response = await client.post(
        "/api/v1/configs",
        json={"external_assignment_id": assignment, "definition": definition()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def outcome(config, *, failed=False, score=0):
    execution_id = "contract-execution"
    value = {
        "schema_version": "1.0",
        "status": "failed" if failed else "completed",
        "execution_id": execution_id,
        "language": "python",
        "provenance": {
            "schema_version": "1.0",
            "reference": str(config["id"]),
            "revision": config["version"],
            "definition_hash": config["definition_hash"],
        },
        "started_at": "2026-10-04T12:00:00Z",
        "finished_at": "2026-10-04T12:00:01Z",
        "duration_ms": 1000,
        "score": None if failed else score,
        "tree": None,
        "error": None,
    }
    if failed:
        value["error"] = {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "The evaluator provider was unavailable.",
            "category": "provider",
            "retryable": True,
            "correlation_id": execution_id,
        }
    else:
        value["tree"] = {
            "name": "root",
            "type": "root",
            "score": score,
            "base": {
                "name": "base",
                "type": "category",
                "weight": 100,
                "score": score,
                "tests": [
                    {
                        "id": "hello",
                        "evaluator": "expect_output",
                        "type": "test",
                        "name": "Hello",
                        "weight": 100,
                        "score": score,
                        "report": "assessed",
                    }
                ],
            },
        }
    return value


def external(config, **kwargs):
    return {
        "grading_config_id": config["id"],
        "external_user_id": "student",
        "username": "Student",
        "language": "python",
        "definition_snapshot": config["definition"],
        "outcome": outcome(config, **kwargs),
    }


@pytest.mark.asyncio
async def test_validation_rejects_before_storage_and_normalizes(test_client):
    invalid = definition()
    invalid["criteria"]["base"]["tests"][0]["parameters"]["locale"] = "en"
    response = await test_client.post(
        "/api/v1/configs", json={"external_assignment_id": "bad", "definition": invalid}
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["path"]
    assert (await test_client.get("/api/v1/configs")).json() == []
    response = await test_client.post("/api/v1/configs/validate", json=definition())
    assert response.status_code == 200
    assert (
        response.json()["definition_hash"]
        == compile_definition(definition()).definition_hash
    )


@pytest.mark.asyncio
async def test_revision_identity_activation_and_nulls(test_client):
    config = await create(test_client)
    endpoint = f'/api/v1/configs/{config["id"]}'
    assert (
        await test_client.patch(endpoint, json={"is_active": False})
    ).status_code == 428
    assert (
        await test_client.patch(
            endpoint, headers={"If-Match": '"1"'}, json={"definition": None}
        )
    ).status_code == 422
    disabled = await test_client.patch(
        endpoint, headers={"If-Match": '"1"'}, json={"is_active": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["version"] == 2
    assert (await test_client.get("/api/v1/configs/assignment")).json()[
        "is_active"
    ] is False
    assert (
        await test_client.get(f'/api/v1/configs/id/{config["id"]}', headers=HEADERS)
    ).json()["version"] == 2
    assert (
        await test_client.post(
            "/api/v1/configs",
            json={"external_assignment_id": "assignment", "definition": definition()},
        )
    ).status_code == 409
    assert (
        await test_client.patch(
            endpoint, headers={"If-Match": '"1"'}, json={"is_active": True}
        )
    ).status_code == 412
    updated = await test_client.patch(
        "/api/v1/configs/external/assignment",
        headers={"If-Match": '"2"'},
        json={"is_active": True},
    )
    assert updated.json()["version"] == 3
    unchanged = await test_client.patch(
        endpoint, headers={"If-Match": '"3"'}, json={"definition": config["definition"]}
    )
    assert unchanged.json()["version"] == 3


@pytest.mark.asyncio
async def test_attestation_retains_historical_snapshot_and_consistent_reads(
    test_client,
):
    config = await create(test_client)
    changed = definition()
    changed["criteria"]["base"]["tests"][0]["name"] = "Renamed"
    update = await test_client.patch(
        f'/api/v1/configs/{config["id"]}',
        headers={"If-Match": '"1"'},
        json={"definition": changed, "is_active": False},
    )
    assert update.json()["version"] == 2
    uploaded = await test_client.post(
        "/api/v1/submissions/external-results",
        headers=HEADERS,
        json=external(config, score=0),
    )
    assert uploaded.status_code == 200, uploaded.text
    identity = uploaded.json()["submission_id"]
    poll = (await test_client.get(f"/api/v1/submissions/{identity}")).json()
    assert poll["final_score"] == 0
    assert poll["language"] == "python"
    assert poll["provenance"]["revision"] == 1
    assert "submission_files" not in poll and "outcome" not in poll
    history = await test_client.get(
        "/api/v1/submissions",
        params={
            "external_user_id": "student",
            "grading_config_id": config["id"],
            "status": "completed",
        },
    )
    assert history.json() == [poll]
    assert (
        await test_client.get(f"/api/v1/submissions/{identity}/details")
    ).status_code == 401
    detail = (
        await test_client.get(
            f"/api/v1/submissions/{identity}/details", headers=HEADERS
        )
    ).json()
    assert detail["outcome"]["score"] == 0
    assert detail["definition_snapshot"] == config["definition"]
    for key in poll:
        assert detail[key] == poll[key]
    assert (
        await test_client.get("/api/v1/submissions", params={"limit": 101})
    ).status_code == 422
    assert (
        await test_client.get("/api/v1/submissions", params={"offset": -1})
    ).status_code == 422


@pytest.mark.asyncio
async def test_provider_failure_is_not_zero_and_invalid_attestation_is_rejected(
    test_client,
):
    config = await create(test_client)
    uploaded = await test_client.post(
        "/api/v1/submissions/external-results",
        headers=HEADERS,
        json=external(config, failed=True),
    )
    assert uploaded.status_code == 200, uploaded.text
    poll = (
        await test_client.get(f'/api/v1/submissions/{uploaded.json()["submission_id"]}')
    ).json()
    assert poll["status"] == "failed" and poll["final_score"] is None
    assert poll["error"]["code"] == "PROVIDER_UNAVAILABLE"
    for mutate in (
        lambda p: p["outcome"].update(score=150),
        lambda p: p["outcome"]["provenance"].update(definition_hash="0" * 64),
        lambda p: p["outcome"]["tree"]["base"]["tests"][0].update(id="other"),
        lambda p: p["outcome"]["tree"]["base"]["tests"][0].update(
            evaluator="dont_fail"
        ),
    ):
        payload = external(config, score=100)
        mutate(payload)
        assert (
            await test_client.post(
                "/api/v1/submissions/external-results", headers=HEADERS, json=payload
            )
        ).status_code == 422


@pytest.mark.asyncio
async def test_acceptance_binds_snapshot_and_multiple_languages_require_choice(
    test_client,
):
    config = await create(test_client)
    payload = {
        "external_assignment_id": "assignment",
        "external_user_id": "student",
        "username": "Student",
        "files": [{"filename": "main.py", "content": "print('Hello')"}],
    }
    with patch(
        "web.api.v1.submissions.grade_submission", new_callable=AsyncMock
    ) as grade:
        response = await test_client.post("/api/v1/submissions", json=payload)
        assert response.status_code == 200, response.text
        import asyncio

        await asyncio.sleep(0)
        request = grade.call_args.args[0]
        assert request.definition == config["definition"]
        assert (
            request.configuration_version == 1
            and request.definition_hash == config["definition_hash"]
        )
    changed = definition()
    changed["languages"] = ["python", "node"]
    assert (
        await test_client.patch(
            f'/api/v1/configs/{config["id"]}',
            headers={"If-Match": '"1"'},
            json={"definition": changed},
        )
    ).status_code == 200
    assert (
        await test_client.post("/api/v1/submissions", json=payload)
    ).status_code == 422


@pytest.mark.asyncio
async def test_all_zero_siblings_match_the_engines_equal_weight_rule(test_client):
    zero = definition()
    zero["criteria"]["base"]["tests"][0]["weight"] = 0
    response = await test_client.post(
        "/api/v1/configs", json={"external_assignment_id": "zero", "definition": zero}
    )
    assert response.status_code == 200, response.text
    payload = external(response.json(), score=100)
    uploaded = await test_client.post(
        "/api/v1/submissions/external-results", headers=HEADERS, json=payload
    )
    assert uploaded.status_code == 200, uploaded.text


def test_openapi_exposes_shared_definition_and_discriminated_outcome():
    from web.main import app

    schema = app.openapi()
    create_schema = schema["components"]["schemas"]["GradingConfigCreate"]
    assert create_schema["properties"]["definition"]["$ref"].endswith(
        "/GradingDefinition-Input"
    )
    external_schema = schema["components"]["schemas"]["ExternalResultCreate"]
    assert (
        external_schema["properties"]["outcome"]["discriminator"]["propertyName"]
        == "status"
    )


from pathlib import Path

EXAMPLES = (
    Path(__file__).resolve().parents[2] / "docs" / "contracts" / "v1" / "examples"
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "example_path", sorted(EXAMPLES.glob("*.json")), ids=lambda path: path.stem
)
async def test_each_published_assignment_type_validates_and_binds_at_http_seam(
    test_client, example_path
):
    import json

    value = json.loads(example_path.read_text())
    response = await test_client.post(
        "/api/v1/configs",
        json={"external_assignment_id": example_path.stem, "definition": value},
    )
    assert response.status_code == 200, response.text
    resource = response.json()
    with patch(
        "web.api.v1.submissions.grade_submission", new_callable=AsyncMock
    ) as grade:
        accepted = await test_client.post(
            "/api/v1/submissions",
            json={
                "external_assignment_id": example_path.stem,
                "external_user_id": "student",
                "username": "Student",
                "language": resource["definition"]["languages"][0],
                "files": [{"filename": "main.py", "content": "print('Hello')"}],
            },
        )
        assert accepted.status_code == 200, accepted.text
        import asyncio

        await asyncio.sleep(0)
        bound = grade.call_args.args[0]
        assert bound.definition == resource["definition"]
        assert bound.definition_hash == resource["definition_hash"]
        assert bound.configuration_version == resource["version"]
