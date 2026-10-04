"""External host attestations obey the same grade/provenance contract."""

import pytest
from tests.web.test_contracts_v1 import create, external, HEADERS, integration_auth


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [-1, 101, float("inf"), float("nan")])
async def test_nonfinite_or_out_of_range_external_scores(test_client, score):
    config = await create(test_client)
    payload = external(config, score=100)
    payload["outcome"]["score"] = score
    # Nonstandard JSON encodings are useful here to exercise the server's validator.
    import json

    response = await test_client.post(
        "/api/v1/submissions/external-results",
        headers={**HEADERS, "Content-Type": "application/json"},
        content=json.dumps(payload),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["definition_snapshot", "outcome", "language", "username", "grading_config_id"],
)
async def test_required_external_fields(test_client, field):
    config = await create(test_client)
    payload = external(config)
    del payload[field]
    assert (
        await test_client.post(
            "/api/v1/submissions/external-results", headers=HEADERS, json=payload
        )
    ).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_language",
        "wrong_language",
        "future_revision",
        "missing_revision",
        "status",
        "error_on_success",
        "score_on_failure",
        "tree_weight",
        "tree_placement",
        "unknown_field",
    ],
)
async def test_inconsistent_attestations(test_client, mutation):
    config = await create(test_client)
    payload = external(config, failed=mutation == "score_on_failure", score=100)
    if mutation == "unknown_language":
        payload["language"] = "ruby"
    elif mutation == "wrong_language":
        payload["language"] = "node"
    elif mutation == "future_revision":
        payload["outcome"]["provenance"]["revision"] = 2
    elif mutation == "missing_revision":
        payload["outcome"]["provenance"]["revision"] = None
    elif mutation == "status":
        payload["outcome"]["status"] = "pending"
    elif mutation == "error_on_success":
        payload["outcome"]["error"] = {
            "code": "ERROR",
            "message": "Failed",
            "category": "internal",
            "retryable": False,
            "correlation_id": "contract-execution",
        }
    elif mutation == "score_on_failure":
        payload["outcome"]["score"] = 0
    elif mutation == "tree_weight":
        payload["outcome"]["tree"]["base"]["tests"][0]["weight"] = 50
    elif mutation == "tree_placement":
        base = payload["outcome"]["tree"]["base"]
        base["subjects"] = [
            {
                "type": "subject",
                "name": "Injected",
                "score": 100,
                "weight": 100,
                "tests": base.pop("tests"),
            }
        ]
    else:
        payload["outcome"]["misspelled_option"] = True
    assert (
        await test_client.post(
            "/api/v1/submissions/external-results", headers=HEADERS, json=payload
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_known_config_required(test_client):
    config = await create(test_client)
    payload = external(config)
    payload["grading_config_id"] = 999
    assert (
        await test_client.post(
            "/api/v1/submissions/external-results", headers=HEADERS, json=payload
        )
    ).status_code == 404
