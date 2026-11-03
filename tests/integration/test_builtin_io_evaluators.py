"""Migrated I/O evaluators grade real programs in real sandbox containers (ARC-03).

Every language image runs the same three built-in evaluators through the
public pipeline and through HTTP plus the durable worker. Commands are
language maps resolved by the evaluator; the session reaches only evaluators
that declare execution.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from autograder import Submission, SubmissionFile, build_pipeline
from execution_host.docker import DockerHost
from sandbox_manager.models.sandbox_models import Language
from tests.web.conftest import db_engine, session_factory  # pylint: disable=unused-import
from web.core.config import Settings
from web.main import create_app

LANGUAGES = ("python", "java", "node", "cpp")
SOURCE = {"python": "main.py", "java": "Main.java", "node": "main.js", "cpp": "main.cpp"}


def program(language, offset=0, crash=False):
    """Sum whitespace-separated integers from stdin, print and write out.txt."""
    if language == "python":
        return ("import sys\nt = sum(int(x) for x in sys.stdin.read().split()) + %d\nprint(t)\n"
                "open('out.txt', 'w').write('sum=%%d\\n' %% t)\n%s" % (offset, "raise RuntimeError('boom')\n" if crash else ""))
    if language == "java":
        return ("import java.util.*;\nimport java.io.*;\npublic class Main {\n  public static void main(String[] a) throws Exception {\n"
                "    Scanner s = new Scanner(System.in); long t = %d;\n    while (s.hasNextLong()) t += s.nextLong();\n"
                "    System.out.println(t);\n    try (PrintWriter w = new PrintWriter(\"out.txt\")) { w.println(\"sum=\" + t); }\n"
                "    %s\n  }\n}\n" % (offset, "throw new RuntimeException(\"boom\");" if crash else ""))
    if language == "node":
        return ("const fs = require('fs');\nconst t = fs.readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean)"
                ".map(Number).reduce((a, b) => a + b, %d);\nconsole.log(String(t));\nfs.writeFileSync('out.txt', 'sum=' + t + '\\n');\n%s"
                % (offset, "throw new TypeError('boom');\n" if crash else ""))
    return ("#include <iostream>\n#include <fstream>\nint main() { long long x, t = %d; while (std::cin >> x) t += x;\n"
            "  std::cout << t << std::endl; std::ofstream(\"out.txt\") << \"sum=\" << t << \"\\n\"; return 0; }\n" % offset)


DEFINITION = {
    "schema_version": "1.0",
    "templates": ["input_output"],
    "languages": list(LANGUAGES),
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "sum", "type": "expect_output", "name": "Sum", "parameters": {
            "inputs": ["2", "3"], "expected_output": "5",
            "program_command": {"python": "python3 main.py", "java": "java Main", "node": "node main.js", "cpp": "./main"}}},
        {"id": "no-crash", "type": "dont_fail", "name": "Does not crash", "parameters": {
            "user_input": "4",
            "program_command": {"python": "python3 main.py", "java": "java Main", "node": "node main.js", "cpp": "./main"}}},
        {"id": "artifact", "type": "expect_file_artifact", "name": "Writes result", "parameters": {
            "inputs": ["2", "3"], "artifact_path": "out.txt", "expected_content": "sum=5",
            "program_command": {"python": "python3 main.py", "java": "java Main", "node": "node main.js", "cpp": "./main"}}},
    ]}},
    "preparation": {"languages": {
        "java": {"required_files": ["Main.java"], "setup_commands": [{"name": "compile", "command": "javac Main.java"}]},
        "cpp": {"required_files": ["main.cpp"], "setup_commands": [{"name": "compile", "command": "g++ main.cpp -o main"}]},
    }},
}


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text("general:\n  pool_size: 0\n  scale_limit: 2\n  idle_timeout: 300\n  running_timeout: 60\n")
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def run(host, language, content):
    pipeline = build_pipeline(definition=DEFINITION, capabilities=host.capabilities)
    name = SOURCE[language]
    return pipeline.run(Submission("student", "student", "io", {name: SubmissionFile(name, content)},
                                   language=Language(language))).outcome


def scores(outcome):
    return {test.id: test.score for test in outcome.tree.base.tests}


@pytest.mark.parametrize("language", LANGUAGES)
def test_correct_program_passes_every_io_evaluator(docker_host, language):
    outcome = run(docker_host, language, program(language))
    assert outcome.status == "completed", outcome.error
    assert scores(outcome) == {"sum": 100, "no-crash": 100, "artifact": 100}
    assert outcome.tree.base.tests[0].parameters["program_command"]["cpp"] == "./main"


@pytest.mark.parametrize("language", LANGUAGES)
def test_wrong_output_is_an_assessed_partial_grade(docker_host, language):
    outcome = run(docker_host, language, program(language, offset=1))
    assert outcome.status == "completed", outcome.error
    assert scores(outcome) == {"sum": 0, "no-crash": 100, "artifact": 0}
    assert outcome.score == pytest.approx(100 / 3, abs=0.01)
    assert "sum=6" in outcome.tree.base.tests[2].report


@pytest.mark.parametrize("language", ("python", "java", "node"))
def test_runtime_crash_is_an_assessed_zero(docker_host, language):
    outcome = run(docker_host, language, program(language, crash=True))
    assert outcome.status == "completed", outcome.error
    assert scores(outcome) == {"sum": 0, "no-crash": 0, "artifact": 0}


@pytest.mark.parametrize("language", ("java", "cpp"))
def test_compile_failure_stops_before_assessment(docker_host, language):
    outcome = run(docker_host, language, "this does not compile")
    assert outcome.status == "failed"
    assert outcome.score is None and outcome.tree is None
    assert outcome.error.code == "PREPARATION_FAILED"


@pytest.fixture
async def docker_application(session_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "io-token")
    config = tmp_path / "sandbox.yml"
    config.write_text("general:\n  pool_size: 0\n  scale_limit: 2\n  idle_timeout: 300\n  running_timeout: 60\n")
    owner = DockerHost(mode="local", config_file=str(config))
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts")), session_factory=session_factory,
                     capabilities=owner.capabilities, resource_owner=owner, start_workers=False)
    await app.state.host.start()
    yield app
    await app.state.host.close()


@pytest.mark.asyncio
async def test_http_submissions_grade_io_evaluators_in_real_containers(docker_application):
    headers = {"Authorization": "Bearer io-token"}
    async with AsyncClient(transport=ASGITransport(app=docker_application), base_url="http://test") as client:
        created = await client.post("/api/v1/configs", json={"external_assignment_id": "io-http", "definition": DEFINITION})
        assert created.status_code == 200, created.text
        expected = {("python", 0): 100, ("java", 1): pytest.approx(100 / 3, abs=0.01), ("node", 0): 100, ("cpp", 1): pytest.approx(100 / 3, abs=0.01)}
        for (language, offset), score in expected.items():
            accepted = await client.post("/api/v1/submissions", json={
                "external_assignment_id": "io-http", "external_user_id": language, "username": language,
                "language": language, "files": [{"filename": SOURCE[language], "content": program(language, offset)}]})
            assert accepted.status_code == 202, accepted.text
            assert await docker_application.state.host.worker.run_once()
            polled = (await client.get(accepted.headers["Location"])).json()
            assert polled["status"] == "completed", polled
            assert polled["final_score"] == score
            details = (await client.get(f'/api/v1/submissions/{polled["id"]}/details', headers=headers)).json()
            tests = details["outcome"]["tree"]["base"]["tests"]
            assert [test["parameters"] for test in tests] == [test["parameters"] for test in
                                                             created.json()["definition"]["criteria"]["base"]["tests"]]
