"""External attestation preserves the exact schema produced by local grading."""
from copy import deepcopy
import requests

from autograder.autograder import build_pipeline
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language
from tests.e2e.contracts import create_config, poll


def attestation(config):
    pipeline = build_pipeline(definition=config["definition"], provenance=DefinitionProvenance(
        definition_hash=config["definition_hash"], reference=str(config["id"]), revision=config["version"]))
    execution = pipeline.run(Submission(username="external", user_id="external", assignment_id=config["id"],
        language=Language.PYTHON, submission_files={"main.py": SubmissionFile("main.py", "pass")}))
    return {"grading_config_id": config["id"], "definition_snapshot": config["definition"],
        "external_user_id": "external-user", "username": "external", "language": "python",
        "outcome": execution.outcome.model_dump(mode="json"), "submission_metadata": {"source": "action"}}


def test_external_results_ingestion_preserves_exact_outcome(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    payload = attestation(config)
    response = requests.post(api_base_url + "/submissions/external-results", json=payload, headers=auth_headers, timeout=5)
    assert response.status_code == 200, response.text
    result = poll(api_base_url, auth_headers, response.json()["submission_id"])
    assert result["outcome"] == payload["outcome"]
    assert result["submission_metadata"] == {"source": "action"}
    history = requests.get(api_base_url + "/submissions", params={"external_user_id": "external-user", "grading_config_id": config["id"]},
        headers=auth_headers, timeout=5).json()
    assert history[0]["final_score"] == payload["outcome"]["score"]
    assert "submission_files" not in history[0] and "outcome" not in history[0]


def test_invalid_external_score_and_definition_hash_are_rejected(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    payload = attestation(config)
    bad = deepcopy(payload)
    bad["outcome"]["score"] = 150
    assert requests.post(api_base_url + "/submissions/external-results", json=bad, headers=auth_headers, timeout=5).status_code == 422
    bad = deepcopy(payload)
    bad["outcome"]["provenance"]["definition_hash"] = "0" * 64
    assert requests.post(api_base_url + "/submissions/external-results", json=bad, headers=auth_headers, timeout=5).status_code == 422
    assert requests.post(api_base_url + "/submissions/external-results", json=payload, timeout=5).status_code == 401
