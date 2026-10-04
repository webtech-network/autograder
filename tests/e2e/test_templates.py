"""Live HTTP → compiled definition → real engine/sandbox → shared outcome."""
import pytest
import requests

from tests.e2e.contracts import create_config, definition, poll, submit


@pytest.mark.parametrize("code,evaluator,parameters,score", [
    ("print('HELLO')", "expect_output", {"inputs": [], "expected_output": "HELLO", "program_command": "python3 main.py"}, 100),
    ("print('WRONG')", "expect_output", {"inputs": [], "expected_output": "HELLO", "program_command": "python3 main.py"}, 0),
    ("import sys; sys.exit(0)", "dont_fail", {"user_input": "", "program_command": "python3 main.py"}, 100),
    ("if True print('HI')", "expect_output", {"inputs": [], "expected_output": "HELLO", "program_command": "python3 main.py"}, 0),
])
def test_io_scenarios(api_base_url, auth_headers, code, evaluator, parameters, score):
    config = create_config(api_base_url, auth_headers, definition("input_output", tests=[
        {"id": "program", "name": "Program", "type": evaluator, "parameters": parameters}]))
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": code}])
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["status"] == "completed"
    assert result["outcome"]["score"] == score
    assert result["outcome"]["tree"]["base"]["tests"][0]["id"] == "program"
    assert result["provenance"]["definition_hash"] == config["definition_hash"]


@pytest.mark.parametrize("filename,content,evaluator,parameters,score", [
    ("index.html", "<h1>Hi</h1>", "has_tag", {"tag": "h1", "required_count": 1}, 100),
    ("index.html", "<h1 style='color:red'></h1>", "check_no_inline_styles", {}, 0),
    ("index.html", "<img src='x.png'>", "check_all_images_have_alt", {}, 0),
    ("style.css", ".c { display: flex; }", "check_flexbox_usage", {}, 100),
    ("index.html", "<blink></blink>", "has_forbidden_tag", {"tag": "blink"}, 0),
])
def test_web_dev_variations(api_base_url, auth_headers, filename, content, evaluator, parameters, score):
    config = create_config(api_base_url, auth_headers, definition("webdev", "node", tests=[
        {"id": "markup", "name": "Markup", "type": evaluator, "parameters": parameters}]))
    accepted = submit(api_base_url, auth_headers, config, [{"filename": filename, "content": content}])
    assert poll(api_base_url, auth_headers, accepted["id"])["outcome"]["score"] == score


def test_api_missing_http_host_capability_is_failed_not_assessed_zero(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers, definition("api", tests=[
        {"id": "health", "name": "Health", "type": "health_check", "parameters": {"endpoint": "/health"}}]))
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "server.py", "content": "pass"}])
    outcome = poll(api_base_url, auth_headers, accepted["id"])["outcome"]
    assert outcome["status"] == "failed"
    assert outcome["score"] is None
    assert outcome["tree"] is None
    assert outcome["error"]["category"] == "capability"


def test_static_analysis_basic_and_selected_capabilities(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers, definition(tests=[
        {"id": "imports", "name": "No OS", "type": "forbidden_import", "parameters": {"forbidden_imports": ["os"]}},
        {"id": "loop", "name": "No Loop", "type": "forbidden_keyword", "parameters": {"forbidden_keywords": ["for_loop"]}},
    ]))
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "import os"}])
    outcome = poll(api_base_url, auth_headers, accepted["id"])["outcome"]
    assert outcome["status"] == "completed" and outcome["score"] == 50
    assert outcome["feedback"]["status"] == "disabled"


def test_disallowed_language_is_rejected_before_acceptance(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers, definition(language="java", tests=[
        {"id": "imports", "name": "Imports", "type": "forbidden_import", "parameters": {"forbidden_imports": ["java.util"]}}]))
    response = requests.post(api_base_url + "/submissions", headers=auth_headers, timeout=5, json={
        "external_assignment_id": config["external_assignment_id"], "external_user_id": "language-mismatch",
        "username": "student", "language": "python", "files": [{"filename": "main.py", "content": "pass"}]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "LANGUAGE_NOT_ALLOWED"


def test_missing_required_files_fail_without_grade(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers, definition(preparation={"languages": {
        "python": {"required_files": ["missing.py"]}}}))
    accepted = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "pass"}])
    outcome = poll(api_base_url, auth_headers, accepted["id"])["outcome"]
    assert outcome["status"] == "failed" and outcome["score"] is None
    assert outcome["error"]["category"] == "submission"


def test_catalog_exposes_same_evaluator_parameter_contract(api_base_url, auth_headers):
    response = requests.get(api_base_url + "/templates/webdev", headers=auth_headers, timeout=5)
    assert response.status_code == 200
    evaluators = {item["identifier"]: item for item in response.json()["evaluators"]}
    schema = evaluators["has_tag"]["parameters_schema"]
    assert schema["additionalProperties"] is False
    assert "tag" in schema["required"]
