"""INT-01 against a real API process: one trust boundary for every resource and alias."""
import requests

from tests.e2e.contracts import create_config, poll, submit
from tests.e2e.test_external_results import attestation


def _walk(api_base_url, config, submission_id):
    """Every route that exposes or changes protected data, with a concrete method/body."""
    alias = config["external_assignment_id"]
    return [
        ("GET", f"/configs/id/{config['id']}", None),
        ("GET", f"/configs/{alias}", None),
        ("GET", "/configs", None),
        ("POST", "/configs", {"external_assignment_id": alias + "-x", "definition": config["definition"]}),
        ("POST", "/configs/validate", config["definition"]),
        ("PATCH", f"/configs/{config['id']}", {"is_active": False}),
        ("PATCH", f"/configs/external/{alias}", {"is_active": False}),
        ("POST", "/submissions", {"external_assignment_id": alias, "external_user_id": "x",
                                  "username": "x", "files": [{"filename": "main.py", "content": "pass"}]}),
        ("GET", f"/submissions/{submission_id}", None),
        ("GET", f"/submissions/{submission_id}/details", None),
        ("GET", "/submissions", None),
        ("GET", "/submissions/user/student", None),
        ("POST", "/execute", {"language": "python", "submission_files": [{"filename": "main.py", "content": "print(1)"}],
                              "program_command": "python main.py"}),
    ]


def test_every_protected_route_rejects_anonymous_and_restricted_callers(api_base_url, auth_headers, producer_headers):
    config = create_config(api_base_url, auth_headers)
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "SECRET = 'e2e-source'"}])
    for method, path, body in _walk(api_base_url, config, accepted["id"]):
        for headers, expected in (({}, 401), ({"Authorization": "Bearer not-the-token"}, 401),
                                  (producer_headers, 403)):
            response = requests.request(method, api_base_url + path, json=body,
                                        headers={**headers, "If-Match": '"1"'}, timeout=10)
            assert response.status_code == expected, (method, path, headers, response.text)
            assert "e2e-source" not in response.text
    # None of the rejected mutations took effect.
    current = requests.get(f"{api_base_url}/configs/id/{config['id']}", headers=auth_headers, timeout=5).json()
    assert current["version"] == 1 and current["is_active"] is True
    history = requests.get(api_base_url + "/submissions/user/x", headers=auth_headers, timeout=5).json()
    assert history == []
    details = requests.get(f"{api_base_url}/submissions/{accepted['id']}/details", headers=auth_headers, timeout=5)
    assert "e2e-source" in details.text
    assert poll(api_base_url, auth_headers, accepted["id"])["status"] in ("completed", "failed")


def test_public_routes_and_readiness(api_base_url):
    assert requests.get(api_base_url + "/health", timeout=5).status_code == 200
    templates = requests.get(api_base_url + "/templates", timeout=5)
    assert templates.status_code == 200 and templates.json()["templates"]
    ready = requests.get(api_base_url + "/ready", timeout=5)
    assert ready.status_code == 200
    assert ready.json()["authentication"] == "configured"


def test_restricted_producer_can_attest_but_not_read(api_base_url, auth_headers, producer_headers):
    config = create_config(api_base_url, auth_headers)
    response = requests.post(api_base_url + "/submissions/external-results", json=attestation(config),
                             headers=producer_headers, timeout=10)
    assert response.status_code == 200, response.text
    submission_id = response.json()["submission_id"]
    assert requests.get(f"{api_base_url}/submissions/{submission_id}", headers=producer_headers,
                        timeout=5).status_code == 403
    readable = requests.get(f"{api_base_url}/submissions/{submission_id}", headers=auth_headers, timeout=5)
    assert readable.status_code == 200 and readable.json()["status"] == "completed"


def test_openapi_documents_bearer_security(api_base_url):
    schema = requests.get(api_base_url.removesuffix("/api/v1") + "/openapi.json", timeout=5).json()
    assert schema["paths"]["/api/v1/configs/{external_assignment_id}"]["get"]["security"] == [{"IntegrationBearer": []}]
    assert "security" not in schema["paths"]["/api/v1/health"]["get"]
