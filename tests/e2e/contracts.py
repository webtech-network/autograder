"""Small HTTP fixture helpers; requests use the production wire contracts."""
import time
from uuid import uuid4

import requests

from autograder.models.contracts.outcome import validate_outcome


def definition(template="static_analysis", language="python", tests=None, preparation=None):
    value = {"schema_version": "1.0", "templates": [template], "languages": [language],
        "criteria": {"base": {"weight": 100, "tests": tests or [
            {"id": "imports", "name": "Imports", "type": "forbidden_import",
             "parameters": {"forbidden_imports": ["os"]}}]}}}
    if preparation:
        value["preparation"] = preparation
    return value


def create_config(url, headers, value=None):
    payload = {"external_assignment_id": "e2e-" + uuid4().hex, "definition": value or definition()}
    response = requests.post(url + "/configs", json=payload, headers=headers, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()


def submit(url, headers, config, files, **extra):
    payload = {"external_assignment_id": config["external_assignment_id"],
        "external_user_id": "e2e-" + uuid4().hex, "username": "student", "files": files, **extra}
    response = requests.post(url + "/submissions", json=payload, headers=headers, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()


def poll(url, headers, submission_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(f"{url}/submissions/{submission_id}", headers=headers, timeout=5)
        assert response.status_code == 200, response.text
        value = response.json()
        # Compact polling must never bring back source files or the result tree.
        assert "submission_files" not in value and "outcome" not in value
        if value["status"] in ("completed", "failed"):
            details = requests.get(f"{url}/submissions/{submission_id}/details", headers=headers, timeout=5)
            assert details.status_code == 200, details.text
            data = details.json()
            validate_outcome(data["outcome"])
            assert value["final_score"] == data["outcome"]["score"]
            assert value["provenance"] == data["outcome"]["provenance"]
            return data
        time.sleep(0.05)
    raise AssertionError(f"Submission {submission_id} did not finish within {timeout}s")
