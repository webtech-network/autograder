"""HTTP details carry a submission failure's explanation; compact projections stay compact (ONB-02).

The execution session is faked at the host seam (the sandbox is external to this
tier); tests/integration/test_submission_explanations_docker.py runs the same
flow through real Docker sandboxes.
"""
# pylint: disable=missing-function-docstring
import asyncio

import pytest

from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.outcome import MAX_REPORT_BYTES, text_bytes
from tests.process_results import exited

HEADERS = {"Authorization": "Bearer explain-token"}
COMPILER = "Main.java:3: error: ';' expected\n" * 2_000


class CompilerSession:
    """The compile step fails with a flood of compiler output."""

    def prepare_workdir(self, files):
        pass

    def run_process(self, request):
        return exited(stderr=COMPILER, code=1)

    def close(self):
        pass


DEFINITION = {
    "schema_version": "1.0", "templates": ["input_output"], "languages": ["java"],
    "preparation": {"languages": {"java": {"required_files": ["Main.java"],
                                           "setup_commands": [{"name": "compile", "command": "javac Main.java"}]}}},
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "runs", "type": "dont_fail", "name": "Runs", "parameters": {"program_command": "java Main"}}]}},
}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "explain-token")


@pytest.fixture
def compiler(application):
    application.state.host.capabilities = HostCapabilities(execution=lambda language: CompilerSession())
    application.state.host.worker.capabilities = application.state.host.capabilities


async def submit(client, application, assignment, filename, locale):
    created = await client.post("/api/v1/configs", json={"external_assignment_id": assignment, "definition": DEFINITION})
    assert created.status_code in (200, 201), created.text
    submitted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": assignment, "external_user_id": "student-1", "username": "Student",
        "locale": locale, "files": [{"filename": filename, "content": "class Main { int x = 1 }"}]})
    assert submitted.status_code == 202, submitted.text
    for _ in range(100):
        if await application.state.host.worker.run_once():
            break
        await asyncio.sleep(0.02)
    submission_id = submitted.json()["id"]
    polled = (await client.get(f"/api/v1/submissions/{submission_id}")).json()
    history = (await client.get("/api/v1/submissions", params={"external_user_id": "student-1"})).json()
    details = await client.get(f"/api/v1/submissions/{submission_id}/details", headers=HEADERS)
    assert details.status_code == 200, details.text
    [listed] = [item for item in history if item["id"] == submission_id]
    return polled, listed, details.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("locale,message", [
    ("en", "The setup step 'compile' failed with exit code 1, so the submission could not be graded."),
    ("pt-br", "A etapa de preparação 'compile' falhou com código de saída 1, então a submissão não pôde ser avaliada."),
])
async def test_details_carry_the_compiler_excerpt_and_polling_stays_compact(client, application, compiler,
                                                                            locale, message):
    polled, listed, details = await submit(client, application, f"explain-{locale}", "Main.java", locale)
    for compact in (polled, listed):
        assert compact["status"] == "failed" and compact["final_score"] is None
        assert compact["error"]["code"] == "PREPARATION_FAILED"
        assert compact["error"]["message"] == message
        assert "output" not in compact["error"]
    error = details["outcome"]["error"]
    assert (error["code"], error["category"], error["message"]) == ("PREPARATION_FAILED", "submission", message)
    assert error["output"].startswith("Main.java:3: error: ';' expected\n")
    assert "bytes omitted" in error["output"] and text_bytes(error["output"]) <= MAX_REPORT_BYTES
    assert details["outcome"]["score"] is None and details["outcome"]["tree"] is None


@pytest.mark.asyncio
async def test_missing_file_is_named_in_compact_and_details(client, application, compiler):
    polled, listed, details = await submit(client, application, "explain-missing", "main.java", "pt-br")
    expected = "Arquivo obrigatório não encontrado: Main.java. Envie-o exatamente com este nome e caminho."
    assert polled["error"]["message"] == listed["error"]["message"] == expected
    assert details["outcome"]["error"]["message"] == expected
    assert "output" not in details["outcome"]["error"]
