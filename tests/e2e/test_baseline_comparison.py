"""Opaque HTTP baselines are retired; explicit attested enrichment stays typed."""
import requests

from tests.e2e.contracts import create_config, poll, submit
from tests.e2e.test_external_results import attestation


def test_opaque_baseline_tree_is_rejected(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    response = requests.post(api_base_url + "/submissions", headers=auth_headers, timeout=5, json={
        "external_assignment_id": config["external_assignment_id"], "external_user_id": "baseline",
        "username": "student", "files": [{"filename": "main.py", "content": "pass"}],
        "baseline_result_tree": {"arbitrary": "unbound"}})
    assert response.status_code == 422
    assert any(item["path"][-1] == "baseline_result_tree" for item in response.json()["detail"])


def test_comparison_disabled_without_bound_baseline_and_vector_derivable(api_base_url, auth_headers):
    from autograder.models.contracts.outcome import validate_outcome, outcome_score_vector
    config = create_config(api_base_url, auth_headers)
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "import os"}])
    outcome = validate_outcome(poll(api_base_url, auth_headers, accepted["id"])["outcome"])
    assert outcome.comparison.status == "disabled"
    assert outcome_score_vector(outcome) == {"imports": 0}


def test_external_comparison_enrichment_preserved_as_shared_outcome(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    payload = attestation(config)
    payload["outcome"]["comparison"] = {"status": "completed", "content": {
        "score_delta": 100, "improved": True, "test_deltas": [{"path": "imports", "status": "improved",
            "baseline_score": 0, "head_score": 100, "delta": 100}]}, "error": None}
    response = requests.post(api_base_url + "/submissions/external-results", json=payload, headers=auth_headers, timeout=5)
    assert response.status_code == 200, response.text
    outcome = poll(api_base_url, auth_headers, response.json()["submission_id"])["outcome"]
    assert outcome["comparison"] == payload["outcome"]["comparison"]
