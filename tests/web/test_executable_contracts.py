"""Published examples cross the real definition, grader, adapter and SQL seams."""

from copy import deepcopy
from pathlib import Path
import re
import asyncio
from unittest.mock import patch

import pytest
import yaml

from examples.contracts.http_round_trip import DEFINITION, round_trip as published_round_trip
from github_action.github_action_service import GithubActionService
from autograder.models.dataclass.submission import SubmissionFile
from web.schemas.submission import ExternalResultCreate


HEADERS = {"Authorization": "Bearer conformance-token"}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "conformance-token")
    monkeypatch.setenv("WEB_OUTCOME_RECEIPT_DIR", str(tmp_path / "receipts"))


async def round_trip(client, assignment, application):
    """Exercise the published client while a real durable worker services its job."""
    async def process():
        for _ in range(100):
            if await application.state.host.worker.run_once():
                return
            await asyncio.sleep(0.02)
    worker = asyncio.create_task(process())
    try:
        return await published_round_trip(client, assignment)
    finally:
        await worker


@pytest.mark.asyncio
async def test_documented_http_round_trip_grades_and_polls_without_mocking_execution(test_client, application):
    polled = await round_trip(test_client, "documented-http", application)
    assert polled["status"] == "completed"
    assert polled["final_score"] == 100
    assert polled["error"] is None
    detail = await test_client.get(
        f'/api/v1/submissions/{polled["id"]}/details', headers=HEADERS
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["outcome"]["score"] == polled["final_score"]
    assert detail.json()["outcome"]["provenance"] == polled["provenance"]


@pytest.mark.asyncio
async def test_action_attestation_and_http_execution_have_the_same_polling_outcome(test_client, application):
    normal = await round_trip(test_client, "shared-contract", application)
    config = (await test_client.get("/api/v1/configs/shared-contract")).json()
    service = GithubActionService()
    with patch("github_action.github_action_service.CloudClient") as client:
        client.return_value.get_grading_config.return_value = config
        pipeline = service.configure(
            definition_path=Path("unused.json"),
            execution_mode="external",
            grading_config_id=config["id"],
            cloud_url="https://cloud.invalid",
            cloud_token="test-token",
            upload_to_cloud=True,
            language=None,
            locale="en",
        )
    action_outcome = service.run_autograder(
        pipeline,
        "Walkthrough Student",
        {"index.html": SubmissionFile("index.html", "<h1>Hello</h1>")},
    )
    payload = service.delivery_payload(action_outcome, "Walkthrough Student")
    ExternalResultCreate.model_validate(payload)
    uploaded = await test_client.post(
        "/api/v1/submissions/external-results", headers=HEADERS, json=payload
    )
    assert uploaded.status_code == 200, uploaded.text
    action_poll = (await test_client.get(
        f'/api/v1/submissions/{uploaded.json()["submission_id"]}'
    )).json()
    for field in ("status", "final_score", "language", "provenance", "error"):
        assert action_poll[field] == normal[field]
    details = (await test_client.get(
        f'/api/v1/submissions/{action_poll["id"]}/details', headers=HEADERS
    )).json()
    assert details["outcome"]["tree"]["base"]["tests"][0]["id"] == "html-entry"
    assert details["outcome"]["score"] == normal["final_score"]

    invalid = deepcopy(payload)
    invalid["outcome"]["provenance"]["definition_hash"] = "0" * 64
    rejected = await test_client.post(
        "/api/v1/submissions/external-results", headers=HEADERS, json=invalid
    )
    assert rejected.status_code == 422
    assert (await test_client.post(
        "/api/v1/submissions/external-results", json=payload
    )).status_code == 401


def test_trusted_python_extension_runs_both_success_and_assessed_failure():
    from examples.contracts.custom_evaluator import grade

    passed = grade("Hello")
    missed = grade("Goodbye")
    assert passed.status == missed.status == "completed"
    assert passed.score == 100
    assert missed.score == 0


@pytest.mark.asyncio
async def test_failed_attestation_polls_as_failure_and_not_as_zero(test_client, application):
    await round_trip(test_client, "failed-attestation", application)
    config = (await test_client.get("/api/v1/configs/failed-attestation")).json()
    service = GithubActionService()
    with patch("github_action.github_action_service.CloudClient") as client:
        client.return_value.get_grading_config.return_value = config
        pipeline = service.configure(
            definition_path=Path("unused.json"), execution_mode="external",
            grading_config_id=config["id"], cloud_url="https://cloud.invalid",
            cloud_token="test-token", upload_to_cloud=True, language=None, locale="en",
        )
    completed = service.run_autograder(
        pipeline, "Walkthrough Student",
        {"index.html": SubmissionFile("index.html", "<h1>Hello</h1>")},
    )
    payload = service.delivery_payload(completed, "Walkthrough Student")
    failed = deepcopy(payload)
    outcome = failed["outcome"]
    outcome.update(
        status="failed", score=None, tree=None,
        error={
            "code": "PROVIDER_UNAVAILABLE",
            "message": "The evaluator provider was unavailable.",
            "category": "provider",
            "retryable": True,
            "correlation_id": outcome["execution_id"],
        },
    )
    response = await test_client.post(
        "/api/v1/submissions/external-results", headers=HEADERS, json=failed
    )
    assert response.status_code == 200, response.text
    polled = (await test_client.get(
        f'/api/v1/submissions/{response.json()["submission_id"]}'
    )).json()
    assert polled["status"] == "failed"
    assert polled["final_score"] is None
    assert polled["error"]["retryable"] is True


def test_advertised_http_routes_exist_in_generated_openapi():
    from web.main import app

    root = Path(__file__).resolve().parents[2]
    advertised = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in ("docs/API.md", "docs/contracts/CONFORMANCE.md", "web/README.md")
    )
    operations = app.openapi()["paths"]

    def same_path(advertised_path, actual_path):
        left, right = advertised_path.split("/"), actual_path.split("/")
        return len(left) == len(right) and all(
            a == b or (a.startswith("{") and b.startswith("{"))
            for a, b in zip(left, right)
        )

    routes = re.findall(r"\b(GET|POST|PATCH|PUT|DELETE) (/api/v1/[\w/{}-]+)", advertised)
    assert routes
    for method, path in routes:
        assert any(
            same_path(path, actual) and method.lower() in verbs
            for actual, verbs in operations.items()
        ), f"Advertised route has no matching operation: {method} {path}"


def test_complete_action_workflows_use_shipped_inputs():
    root = Path(__file__).resolve().parents[2]
    action = yaml.safe_load((root / "action.yml").read_text(encoding="utf-8"))
    for doc in ("quick-start.md", "external-mode.md"):
        text = (root / "docs/github_action" / doc).read_text(encoding="utf-8")
        workflow = yaml.safe_load(text.split("```yaml\n", 1)[1].split("```", 1)[0])
        steps = workflow["jobs"]["assess"]["steps"]
        assert steps[0]["uses"] == "actions/checkout@v4"
        inputs = steps[1]["with"]
        assert steps[1]["uses"] == "webtech-network/autograder@main"
        assert set(inputs) <= set(action["inputs"])
        assert any(step["uses"] == "actions/upload-artifact@v4" for step in steps)
