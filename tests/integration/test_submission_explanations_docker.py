"""Real Java and C sandboxes: an ungradable submission says why (ONB-02).

The documented compiled-language pattern compiles in a setup command. A
submission that does not compile, or is missing a required file, stays a failed
grading with no score, and its error names the step or file in the submission's
locale with a bounded excerpt of the compiler output. An infrastructure failure
injected at the session seam still exposes nothing but its fixed message.
"""
import json
import re

import pytest
from httpx import ASGITransport, AsyncClient

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.outcome import MAX_REPORT_BYTES, text_bytes, validate_outcome
from autograder.models.language import Language
from execution_host.docker import DockerHost
from github_action import main as action
from tests.sandbox_profiles import sandbox_config
from tests.web.conftest import db_engine, session_factory  # pylint: disable=unused-import
from web.core.config import Settings
from web.main import create_app

SOURCE = {"java": "Main.java", "c": "main.c"}
COMPILE = {"java": "javac Main.java", "c": "gcc main.c -o main"}
RUN = {"java": "java Main", "c": "./main"}
BROKEN = {"java": "public class Main {\n  public static void main(String[] a) {\n    int x = 1\n  }\n}\n",
          "c": "int main(void) {\n  int x = 1\n  return x;\n}\n"}
# The compiler's own words for BROKEN: the excerpt must be the real output.
DIAGNOSTIC = {"java": re.compile(r"Main\.java:3: error: ';' expected"),
              "c": re.compile(r"main\.c:\d+:\d+: error: expected '[;,]'")}
MESSAGE = {"en": "The setup step 'compile' failed with exit code 1, so the submission could not be graded.",
           "pt-br": ("A etapa de preparação 'compile' falhou com código de saída 1, "
                     "então a submissão não pôde ser avaliada.")}
LANGUAGES = ("java", "c")


def definition(language, **step):
    return {"schema_version": "1.0", "templates": ["input_output"], "languages": [language],
            "preparation": {"languages": {language: {
                "required_files": [SOURCE[language]],
                "setup_commands": [{"name": "compile", "command": COMPILE[language], **step}]}}},
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": "runs", "type": "dont_fail", "name": "Runs", "parameters": {"program_command": RUN[language]}}]}}}


@pytest.fixture(scope="module")
def sandbox_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    path.write_text(sandbox_config((Language.JAVA, Language.C)))
    return path


@pytest.fixture(scope="module")
def docker_host(sandbox_file):
    host = DockerHost(mode="local", config_file=str(sandbox_file))
    yield host
    host.close()


def grade(capabilities, language, files, *, locale="en", **step):
    outcome = build_pipeline(definition=definition(language, **step), capabilities=capabilities).run(Submission(
        "student", "student", "explain", {name: SubmissionFile(name, content) for name, content in files.items()},
        language=Language(language), locale=locale)).outcome
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert validate_outcome(outcome.model_dump(mode="json")) == outcome
    return outcome.error


@pytest.mark.parametrize("locale", ["en", "pt-br"])
@pytest.mark.parametrize("language", LANGUAGES)
def test_non_compiling_submission_shows_the_step_and_compiler_output(docker_host, language, locale):
    error = grade(docker_host.capabilities, language, {SOURCE[language]: BROKEN[language]}, locale=locale)
    assert (error.code, error.category, error.retryable) == ("PREPARATION_FAILED", "submission", False)
    assert error.message == MESSAGE[locale]
    assert DIAGNOSTIC[language].search(error.output), error.output
    assert "bytes omitted" not in error.output


@pytest.mark.parametrize("language", LANGUAGES)
def test_compiler_flood_is_excerpted_to_the_report_bound(docker_host, language):
    lines = "\n".join(f"  int v{index} = ;" for index in range(3_000))
    source = (f"public class Main {{\n  void f() {{\n{lines}\n  }}\n}}\n" if language == "java"
              else f"void f(void) {{\n{lines}\n}}\nint main(void) {{ return 0; }}\n")
    # javac stops after 100 errors unless told otherwise; the step is the author's choice.
    step = {"command": "javac -Xmaxerrs 100000 Main.java"} if language == "java" else {}
    error = grade(docker_host.capabilities, language, {SOURCE[language]: source}, **step)
    assert error.code == "PREPARATION_FAILED"
    assert text_bytes(error.output) <= MAX_REPORT_BYTES
    omitted, total = map(int, re.search(r"\[\.\.\. (\d+) of (\d+) bytes omitted \.\.\.\]", error.output).groups())
    assert total > 10 * MAX_REPORT_BYTES and omitted > total - MAX_REPORT_BYTES
    assert DIAGNOSTIC[language].pattern.split(":")[0].replace("\\", "") in error.output


@pytest.mark.parametrize("locale,expected", [
    ("en", "Required file not found: {file}. Submit it with exactly this name and path."),
    ("pt-br", "Arquivo obrigatório não encontrado: {file}. Envie-o exatamente com este nome e caminho."),
])
@pytest.mark.parametrize("language", LANGUAGES)
def test_missing_required_file_is_named(docker_host, language, locale, expected):
    misnamed = SOURCE[language].swapcase()
    error = grade(docker_host.capabilities, language, {misnamed: BROKEN[language]}, locale=locale)
    assert (error.code, error.category) == ("REQUIRED_FILE_MISSING", "submission")
    assert error.message == expected.format(file=SOURCE[language])
    assert error.output is None


@pytest.mark.parametrize("language", LANGUAGES)
def test_private_output_step_keeps_the_compiler_output_out(docker_host, language):
    error = grade(docker_host.capabilities, language, {SOURCE[language]: BROKEN[language]}, private_output=True)
    assert error.message == MESSAGE["en"]
    assert error.output is None
    assert SOURCE[language] not in json.dumps(error.model_dump(mode="json"))


class FailingTransport:
    """A real sandbox session whose process transport fails, as a host fault would."""

    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)

    def run_process(self, request):
        raise RuntimeError("docker exec failed: /var/lib/docker/overlay2/SECRET-PATH")


@pytest.mark.parametrize("locale", ["en", "pt-br"])
@pytest.mark.parametrize("language", LANGUAGES)
def test_infrastructure_failure_at_the_session_seam_exposes_no_detail(docker_host, language, locale):
    capabilities = HostCapabilities(execution=lambda lang: FailingTransport(docker_host.capabilities.execution(lang)))
    error = grade(capabilities, language, {SOURCE[language]: BROKEN[language]}, locale=locale)
    data = error.model_dump(mode="json")
    data.pop("correlation_id")
    assert data == {"code": "PREPARATION_ERROR", "message": "Assignment preparation could not complete.",
                    "category": "capability", "retryable": True}


@pytest.fixture
async def docker_application(session_factory, sandbox_file, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "explain-token")
    owner = DockerHost(mode="local", config_file=str(sandbox_file))
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), INTEGRATION_TOKEN="explain-token"),
                     session_factory=session_factory, capabilities=owner.capabilities, resource_owner=owner,
                     start_workers=False)
    await app.state.host.start()
    yield app
    await app.state.host.close()


@pytest.mark.asyncio
async def test_http_details_carry_the_compiler_excerpt_and_polling_stays_compact(docker_application):
    headers = {"Authorization": "Bearer explain-token"}
    async with AsyncClient(transport=ASGITransport(app=docker_application), base_url="http://test",
                           headers=headers) as client:
        created = await client.post("/api/v1/configs", json={"external_assignment_id": "explain-http",
                                                             "definition": definition("java")})
        assert created.status_code == 200, created.text
        accepted = await client.post("/api/v1/submissions", json={
            "external_assignment_id": "explain-http", "external_user_id": "s1", "username": "s1", "locale": "pt-br",
            "files": [{"filename": "Main.java", "content": BROKEN["java"]}]})
        assert accepted.status_code == 202, accepted.text
        assert await docker_application.state.host.worker.run_once()
        polled = (await client.get(accepted.headers["Location"])).json()
        assert polled["status"] == "failed" and polled["final_score"] is None
        assert polled["error"]["message"] == MESSAGE["pt-br"] and "output" not in polled["error"]
        details = (await client.get(f'/api/v1/submissions/{polled["id"]}/details')).json()
        assert details["outcome"]["error"]["message"] == MESSAGE["pt-br"]
        assert DIAGNOSTIC["java"].search(details["outcome"]["error"]["output"])


def test_action_summary_and_artifact_carry_the_compiler_excerpt(sandbox_file, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / ".github/autograder").mkdir(parents=True)
    (workspace / "main.c").write_text(BROKEN["c"])
    (workspace / ".github/autograder/definition.json").write_text(json.dumps(definition("c")))
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    monkeypatch.setenv("SANDBOX_MODE", "local")
    monkeypatch.setenv("SANDBOX_CONFIG_FILE", str(sandbox_file))
    assert action.run(action.parser.parse_args(["--submitter-id", "alice", "--locale", "pt-br"])) is False
    outcome = json.loads((workspace / ".autograder/outcome.json").read_text(encoding="utf-8"))
    assert outcome["error"]["message"] == MESSAGE["pt-br"]
    assert DIAGNOSTIC["c"].search(outcome["error"]["output"])
    summary = (tmp_path / "summary").read_text(encoding="utf-8")
    assert f"{MESSAGE['pt-br']} (`PREPARATION_FAILED`)" in summary
    assert "```text\n" + outcome["error"]["output"] + "\n```" in summary
