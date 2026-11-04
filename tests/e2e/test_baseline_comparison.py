"""Comparison is an explicit read of stored canonical outcomes, never a grading input."""
import requests

from tests.e2e.contracts import create_config, definition, poll, submit
from tests.e2e.test_external_results import attestation


def upload(url, headers, payload):
    response = requests.post(url + "/submissions/external-results", json=payload, headers=headers, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()["submission_id"]


def compare(url, headers, head, baseline):
    return requests.get(f"{url}/submissions/{head}/comparison", params={"baseline_submission_id": baseline},
                        headers=headers, timeout=10)


def revise(url, headers, config, value):
    response = requests.patch(f'{url}/configs/{config["id"]}', json={"definition": value},
                              headers={**headers, "If-Match": f'"{config["version"]}"'}, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()


def test_opaque_baseline_tree_is_rejected(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    response = requests.post(api_base_url + "/submissions", headers=auth_headers, timeout=5, json={
        "external_assignment_id": config["external_assignment_id"], "external_user_id": "baseline",
        "username": "student", "files": [{"filename": "main.py", "content": "pass"}],
        "baseline_result_tree": {"arbitrary": "unbound"}})
    assert response.status_code == 422
    assert any(item["path"][-1] == "baseline_result_tree" for item in response.json()["detail"])


def test_attested_outcomes_for_two_revisions_compare_on_demand(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    baseline = upload(api_base_url, auth_headers, attestation(config))
    changed = definition(tests=[
        {"id": "imports", "name": "No os import", "type": "forbidden_import",
         "parameters": {"forbidden_imports": ["os"]}},
        {"id": "no-sys", "name": "No sys import", "type": "forbidden_import",
         "parameters": {"forbidden_imports": ["sys"]}}])
    revised = revise(api_base_url, auth_headers, config, changed)
    assert revised["version"] == 2
    head = upload(api_base_url, auth_headers, attestation(revised))
    stored = [poll(api_base_url, auth_headers, identity)["outcome"] for identity in (baseline, head)]

    assert compare(api_base_url, {}, head, baseline).status_code == 401
    response = compare(api_base_url, auth_headers, head, baseline)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["compatibility"] == "cross_revision"
    assert body["score_delta"] is None and body["improved"] is None
    assert body["changed_definition_sections"] == ["criteria"]
    assert {side: (body[side]["submission_id"], body[side]["source"], body[side]["provenance"]["revision"])
            for side in ("baseline", "head")} == {"baseline": (baseline, "attested", 1), "head": (head, "attested", 2)}
    assert [(row["criterion_id"], row["status"], row["baseline_label"], row["head_label"], row["delta"])
            for row in body["criteria"]] == [
        ("imports", "reweighted", "Imports", "No os import", 0.0),
        ("no-sys", "introduced", None, "No sys import", None)]
    # Retrying is calling again: deterministic and without touching stored grades.
    assert compare(api_base_url, auth_headers, head, baseline).json() == body
    assert [poll(api_base_url, auth_headers, identity)["outcome"] for identity in (baseline, head)] == stored
    assert all(outcome["comparison"] == {"status": "disabled", "content": None, "error": None} for outcome in stored)


def test_executed_and_attested_outcomes_follow_the_same_rules(api_base_url, auth_headers):
    from autograder.models.contracts.outcome import outcome_score_vector, validate_outcome
    config = create_config(api_base_url, auth_headers)
    executed = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "import os"}])["id"]
    outcome = validate_outcome(poll(api_base_url, auth_headers, executed)["outcome"])
    assert outcome.comparison.status == "disabled"
    assert outcome_score_vector(outcome) == {"imports": 0}
    attested = upload(api_base_url, auth_headers, attestation(config))
    body = compare(api_base_url, auth_headers, attested, executed).json()
    assert body["compatibility"] == "same_definition"
    assert (body["score_delta"], body["improved"]) == (100, True)
    assert (body["baseline"]["source"], body["head"]["source"]) == ("executed", "attested")
    assert body["criteria"][0]["status"] == "improved"

    other = create_config(api_base_url, auth_headers)
    foreign = upload(api_base_url, auth_headers, attestation(other))
    response = compare(api_base_url, auth_headers, foreign, executed)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "NOT_COMPARABLE"
    assert compare(api_base_url, auth_headers, 10**9, executed).status_code == 404


def test_attested_comparison_enrichment_is_preserved_but_not_interpreted(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    payload = attestation(config)
    payload["outcome"]["comparison"] = {"status": "completed", "content": {
        "score_delta": 100, "improved": True, "test_deltas": [{"path": "imports", "status": "improved",
            "baseline_score": 0, "head_score": 100, "delta": 100}]}, "error": None}
    identity = upload(api_base_url, auth_headers, payload)
    outcome = poll(api_base_url, auth_headers, identity)["outcome"]
    assert outcome["comparison"] == payload["outcome"]["comparison"]
