"""Built-in evaluators graded over real HTTP calls and the durable worker (ARC-03).

Configurations are created, submissions accepted, graded by the host worker
and read back through authenticated details, without mocking execution.
"""
from copy import deepcopy

import pytest

from tests.builtin_evaluator_cases import DEFINITION, SUBMISSIONS, golden, leaves

HEADERS = {"Authorization": "Bearer builtin-token"}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "builtin-token")


async def create(client, assignment, definition):
    response = await client.post("/api/v1/configs", json={"external_assignment_id": assignment, "definition": definition})
    return response


async def grade(client, application, assignment, files, language=None):
    payload = {"external_assignment_id": assignment, "external_user_id": "student", "username": "Student",
               "files": [{"filename": name, "content": content} for name, content in files.items()]}
    if language:
        payload["language"] = language
    submitted = await client.post("/api/v1/submissions", json=payload)
    assert submitted.status_code == 202, submitted.text
    for _ in range(50):
        if not await application.state.host.worker.run_once():
            break
    polled = (await client.get(submitted.headers["Location"])).json()
    assert polled["status"] in ("completed", "failed"), polled
    details = await client.get(f'/api/v1/submissions/{polled["id"]}/details', headers=HEADERS)
    assert details.status_code == 200, details.text
    return polled, details.json()["outcome"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
async def test_every_static_builtin_grades_over_http_like_the_recorded_engine(test_client, application, variant):
    created = await create(test_client, f"builtins-{variant}", DEFINITION)
    assert created.status_code == 200, created.text
    polled, outcome = await grade(test_client, application, f"builtins-{variant}", SUBMISSIONS[variant])
    expected = golden()[variant]
    assert polled["status"] == "completed" and outcome["error"] is None
    assert polled["final_score"] == expected["score"]
    assert leaves(outcome["tree"]) == expected["criteria"]
    # The reported parameters are the stored canonical snapshot's parameters.
    stored = created.json()["definition"]["criteria"]["base"]["subjects"][0]["tests"]
    reported = outcome["tree"]["base"]["subjects"][0]["tests"]
    assert [test["parameters"] for test in reported] == [test["parameters"] for test in stored]


def single(test, templates, languages=("python",)):
    return {"schema_version": "1.0", "templates": list(templates), "languages": list(languages),
            "criteria": {"base": {"weight": 100, "tests": [test]}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("definition,code,path", [
    (single({"id": "t", "type": "has_tag", "name": "Tag", "parameters": {"tag": ""}}, ["webdev"]),
     "INVALID_DEFINITION", ["parameters", "tag"]),
    (single({"id": "t", "type": "count_global_vars", "name": "Vars", "parameters": {"max_allowed": -1}}, ["webdev"]),
     "INVALID_DEFINITION", ["parameters", "max_allowed"]),
    (single({"id": "k", "type": "forbidden_keyword", "name": "Keywords",
             "parameters": {"forbidden_keywords": ["eval_call"]}}, ["static_analysis"], ("python", "java")),
     "UNSUPPORTED_KEYWORD", ["parameters", "forbidden_keywords", 0]),
    (single({"id": "k", "type": "forbidden_keyword", "name": "Rules",
             "parameters": {"custom_ast_grep_rules": [{"pattern": "x", "bogus": 1}]}}, ["static_analysis"]),
     "INVALID_AST_RULE", ["parameters", "custom_ast_grep_rules", 0]),
    (single({"id": "io", "type": "expect_output", "name": "IO",
             "parameters": {"program_command": {"python": "python3 main.py"}, "expected_output": "x"}},
            ["input_output"], ("python", "java")),
     "MISSING_LANGUAGE_COMMAND", ["parameters", "program_command"]),
])
async def test_evaluator_owned_validation_rejects_configs_over_http(test_client, definition, code, path):
    response = await create(test_client, "invalid", definition)
    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["code"] == code
    assert error["path"][-len(path):] == path


@pytest.mark.asyncio
@pytest.mark.parametrize("definition,files,code", [
    (single({"id": "ai", "type": "ai_sorting_algorithm", "name": "Sort",
             "parameters": {"algorithm_name": "Merge Sort"}}, ["static_analysis"]),
     {"main.py": "def sort(a): return sorted(a)"}, "PROVIDER_UNAVAILABLE"),
    (single({"id": "io", "type": "expect_output", "name": "IO",
             "parameters": {"program_command": "CMD", "expected_output": "x"}}, ["input_output"]),
     {"main.py": "print('x')"}, "CAPABILITY_UNAVAILABLE"),
    (single({"id": "api", "type": "health_check", "name": "Health", "parameters": {"endpoint": "/health"}}, ["api"]),
     {"server.py": "pass"}, "SERVER_CAPABILITY_UNAVAILABLE"),
    (single({"id": "t", "type": "has_tag", "name": "Tag", "file": "missing.html",
             "parameters": {"tag": "main"}}, ["webdev"]),
     {"index.html": "<main></main>"}, "REQUIRED_FILE_MISSING"),
])
async def test_unavailable_or_missing_inputs_fail_without_a_grade_over_http(test_client, application, definition, files, code):
    created = await create(test_client, f"failing-{code.lower()}", definition)
    assert created.status_code == 200, created.text
    polled, outcome = await grade(test_client, application, f"failing-{code.lower()}", files)
    assert polled["status"] == "failed"
    assert polled["final_score"] is None and outcome["tree"] is None
    assert outcome["error"]["code"] == code


@pytest.mark.asyncio
async def test_assessed_static_failure_is_a_valid_zero_over_http(test_client, application):
    definition = single({"id": "imports", "type": "forbidden_import", "name": "Imports",
                         "parameters": {"forbidden_imports": ["os"]}}, ["static_analysis"])
    assert (await create(test_client, "imports", deepcopy(definition))).status_code == 200
    polled, outcome = await grade(test_client, application, "imports", {"main.py": "import os\n"})
    assert polled["status"] == "completed" and polled["final_score"] == 0
    assert "os" in outcome["tree"]["base"]["tests"][0]["report"]
    assert outcome["tree"]["base"]["tests"][0]["parameters"] == {"forbidden_imports": ["os"]}
