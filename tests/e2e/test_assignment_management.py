import requests
import pytest

def test_assignment_crud(api_base_url, auth_headers):
    # 1. Create assignment
    config_payload = {
        "external_assignment_id": "test-assignment-1",
        "template_name": "input_output",
        "criteria_config": {
            "base": {
                "tests": [
                    {"name": "Test 1", "type": "expect_output", "inputs": [], "expected_output": "HELLO\n"}
                ]
            }
        },
        "grading_weights": {"io_match": 1.0},
        "languages": ["python"]
    }
    
    response = requests.post(f"{api_base_url}/configs", json=config_payload, headers=auth_headers)
    assert response.status_code in [200, 201]
    
    # 2. Verify duplicate external_assignment_id returns 400
    response = requests.post(f"{api_base_url}/configs", json=config_payload, headers=auth_headers)
    assert response.status_code == 400
    
    # 3. Retrieve config
    response = requests.get(f"{api_base_url}/configs/test-assignment-1", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["criteria_config"] == config_payload["criteria_config"]
    
    # 4. Update config
    update_payload = {
        "criteria_config": {
            "base": {
                "tests": [
                    {"name": "Test 1 Updated", "type": "expect_output", "inputs": [], "expected_output": "HELLO\n", "weight": 50.0}
                ]
            }
        }
    }
    response = requests.put(f"{api_base_url}/configs/external/test-assignment-1", json=update_payload, headers=auth_headers)
    assert response.status_code == 200
    
    # Verify update
    response = requests.get(f"{api_base_url}/configs/test-assignment-1", headers=auth_headers)
    assert response.json()["criteria_config"]["base"]["tests"][0]["weight"] == 50.0
