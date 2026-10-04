"""Canonical configuration revisions and binding through a live API process."""
from copy import deepcopy
import requests

from tests.e2e.contracts import create_config, definition, poll, submit


def test_assignment_crud(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    response = requests.post(api_base_url + "/configs", json={
        "external_assignment_id": config["external_assignment_id"], "definition": config["definition"]},
        headers=auth_headers, timeout=5)
    assert response.status_code == 409
    fetched = requests.get(f"{api_base_url}/configs/id/{config['id']}", headers=auth_headers, timeout=5)
    assert fetched.status_code == 200
    assert fetched.headers["ETag"] == '"1"'
    assert fetched.json()["definition_hash"] == config["definition_hash"]
    update = deepcopy(config["definition"])
    update["criteria"]["base"]["tests"][0]["name"] = "Updated label"
    path = f"{api_base_url}/configs/{config['id']}"
    assert requests.patch(path, json={"definition": update}, headers=auth_headers, timeout=5).status_code == 428
    response = requests.patch(path, json={"definition": update}, headers={**auth_headers, "If-Match": '"1"'}, timeout=5)
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert response.json()["definition_hash"] != config["definition_hash"]
    assert requests.patch(path, json={"definition": update}, headers={**auth_headers, "If-Match": '"1"'}, timeout=5).status_code == 412


def test_bound_execution_uses_accepted_definition_after_update_and_deactivation(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "import os"}])
    changed = definition()
    changed["criteria"]["base"]["tests"][0]["parameters"] = {"forbidden_imports": ["sys"]}
    response = requests.patch(f"{api_base_url}/configs/{config['id']}", headers={**auth_headers, "If-Match": '"1"'},
        json={"definition": changed, "is_active": False}, timeout=5)
    assert response.status_code == 200, response.text
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["score"] == 0
    assert result["definition_snapshot"] == config["definition"]
    assert result["provenance"]["revision"] == 1
    assert result["provenance"]["definition_hash"] == config["definition_hash"]
    response = requests.post(api_base_url + "/submissions", headers=auth_headers, timeout=5, json={
        "external_assignment_id": config["external_assignment_id"], "external_user_id": "inactive",
        "username": "student", "files": [{"filename": "main.py", "content": "pass"}]})
    assert response.status_code == 409


def test_invalid_definition_returns_parameter_path_before_storage(api_base_url, auth_headers):
    value = definition()
    value["criteria"]["base"]["tests"][0]["parameters"]["forbiden_imports"] = ["sys"]
    response = requests.post(api_base_url + "/configs", headers=auth_headers, timeout=5, json={
        "external_assignment_id": "invalid-parameter", "definition": value})
    assert response.status_code == 422
    assert any(item["path"][-1] == "forbiden_imports" for item in response.json()["detail"])
    assert requests.get(api_base_url + "/configs/invalid-parameter", headers=auth_headers, timeout=5).status_code == 404
