import requests
import pytest

def test_external_results_ingestion(api_base_url, auth_headers):
    config_id = "external-results-test"
    config_payload = {
        "external_assignment_id": config_id,
        "template_name": "input_output",
        "languages": ["python"],
        "criteria_config": {
            "base": {"tests": []}
        }
    }
    response = requests.post(f"{api_base_url}/configs", json=config_payload, headers=auth_headers)
    assert response.status_code in [200, 201, 400]
    config_data = response.json()
    internal_config_id = config_data["id"]
    
    external_payload = {
        "grading_config_id": internal_config_id,
        "external_user_id": "user-external",
        "username": "student-external",
        "language": "python",
        "status": "completed",
        "final_score": 85.0,
        "result_tree": {"manual_check": "passed"},
        "execution_time_ms": 1200,
        "submission_metadata": {"source": "github-action"}
    }
    
    response = requests.post(f"{api_base_url}/submissions/external-results", json=external_payload, headers=auth_headers)
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["status"] == "completed"
    assert data["final_score"] == 85.0
    
    # Verify it appears in history
    response = requests.get(f"{api_base_url}/submissions/user/user-external", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    assert any(sub["grading_config_id"] == internal_config_id for sub in history)
