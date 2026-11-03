"""ARC-08: one process request/result contract for every backend and consumer."""
import importlib
import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autograder import HostCapabilities, Submission, SubmissionFile, build_pipeline
from autograder.models.execution import ExecutionSession
from autograder.models.language import Language
from autograder.models.process import (
    MAX_STDIN_BYTES, ProcessRequest, ProcessResult, ProcessStatus, ResponseCategory, decode_output,
    lines_to_stdin, split_command,
)
from sandbox_manager.api import create_app
from sandbox_manager.models.api_models import ProcessRequestModel, ProcessResultModel
from tests.process_results import exited, not_started, timed_out
from tests.unit.sandbox.fakes import FakeManager

ROOT = Path(__file__).resolve().parents[2]


# ----- request -------------------------------------------------------------------------

def test_command_mode_is_explicit():
    assert ProcessRequest.command('python3 "a b" c\\ d').argv == ("python3", "a b", "c d")
    assert ProcessRequest.command("echo one && echo two").argv == ("echo", "one", "&&", "echo", "two")
    assert ProcessRequest(shell="echo one && echo two").program == ("/bin/sh", "-c", "echo one && echo two")
    for options in ({}, {"argv": ("a",), "shell": "a"}, {"argv": ()}, {"argv": ("",)}, {"shell": " "}):
        with pytest.raises(ValueError):
            ProcessRequest(**options)


@pytest.mark.parametrize("command", ["python3 'main.py", 'echo "x', "echo x\\", "", "   "])
def test_malformed_or_empty_commands_are_errors_never_a_shell(command):
    with pytest.raises(ValueError):
        split_command(command)
    with pytest.raises(ValueError):
        ProcessRequest.command(command)


@pytest.mark.parametrize("options", [
    {"argv": ("a\x00b",)}, {"argv": ("a",), "stdin": b"x" * (MAX_STDIN_BYTES + 1)}, {"argv": ("a",), "stdin": "text"},
    {"argv": ("a",), "cwd": "app"}, {"argv": ("a",), "cwd": "/app/../etc"}, {"argv": ("a",), "timeout": 0},
    {"argv": ("a",), "timeout": 601}, {"argv": ("a",), "max_output_bytes": 0},
])
def test_requests_are_bounded(options):
    with pytest.raises(ValueError):
        ProcessRequest(**options)


@pytest.mark.parametrize("lines,expected", [
    ([], b""), ([""], b"\n"), (["a", "b"], b"a\nb\n"), (["-n"], b"-n\n"), (["a\\nb"], b"a\\nb\n"),
    (["olá"], "olá\n".encode()),
])
def test_lines_become_exact_stdin(lines, expected):
    assert lines_to_stdin(lines) == expected


# ----- result --------------------------------------------------------------------------

@pytest.mark.parametrize("result,category", [
    (exited(), ResponseCategory.SUCCESS),
    (exited(stderr="Traceback (most recent call last):"), ResponseCategory.SUCCESS),  # wording never matters
    (exited(code=1), ResponseCategory.RUNTIME_ERROR),
    (exited(stderr="error: javac", code=2), ResponseCategory.RUNTIME_ERROR),
    (exited(code=137), ResponseCategory.RUNTIME_ERROR),  # not a timeout without evidence
    (timed_out(), ResponseCategory.TIMEOUT),
])
def test_category_depends_only_on_exit_status(result, category):
    assert result.category is category


def test_a_process_that_never_started_has_no_category():
    with pytest.raises(ValueError):
        _ = not_started().category
    assert not not_started().started and not not_started().succeeded


def test_truncated_output_never_ends_in_a_broken_character():
    data = "aé€😀".encode()
    for cut in range(len(data) + 1):
        decoded = decode_output(data[:cut], truncated=True)
        assert "�" not in decoded and "aé€😀".startswith(decoded)
    assert decode_output(b"\xff", truncated=False) == "�"


def test_wire_models_round_trip_the_shared_contract():
    request = ProcessRequest(argv=("python3", "a b"), stdin=b"\x00\n", cwd="/app/sub", timeout=2.5,
                             max_output_bytes=10)
    assert ProcessRequestModel.from_request(request).to_request() == request
    shell = ProcessRequest(shell="echo $HOME | tr a b")
    assert ProcessRequestModel.from_request(shell).to_request() == shell
    for result in (exited("o", "e", 3), timed_out("partial"), not_started("./a.out")):
        assert ProcessResultModel.from_result(result).to_result() == result


def test_control_api_validates_requests_with_the_same_contract():
    manager = FakeManager()
    token = "process-token-" + "p" * 20
    headers = {"Authorization": f"Bearer {token}", "X-Sandbox-Lease": "l" * 40}
    with TestClient(create_app(token=token, manager_factory=lambda: manager)) as client:
        handle = client.post("/sandboxes/python", headers=headers).json()["sandbox_id"]
        for body in ({"argv": ["a"], "shell": "a"}, {}, {"argv": []}, {"argv": ["a"], "stdin": "not base64!"},
                     {"argv": ["a"], "cwd": "relative"}, {"argv": ["a"], "unknown": 1}):
            response = client.post(f"/sandboxes/{handle}/process", headers=headers, json=body)
            assert response.status_code == 422, (body, response.text)
        ok = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["cat"], "stdin": "YQo="})
        assert ok.status_code == 200 and ok.json()["stdout"] == "ran cat\na\n"
        assert manager.leased[0].runs == ["cat"]
        for removed in ("/run", "/run-batch"):
            assert client.post(f"/sandboxes/{handle}{removed}", headers=headers, json={}).status_code in (404, 405)


# ----- one primitive for every consumer -----------------------------------------------

def test_sessions_expose_one_process_operation():
    from execution_host.docker import DockerSession
    from sandbox_manager.remote_client import RemoteSandboxContainer
    from sandbox_manager.sandbox_container import SandboxContainer
    members = {name for name, _ in inspect.getmembers(ExecutionSession) if not name.startswith("_")}
    assert "run_process" in members and not {"run_command", "run_commands"} & members
    for implementation in (DockerSession, SandboxContainer, RemoteSandboxContainer):
        assert hasattr(implementation, "run_process")
        assert not hasattr(implementation, "run_command") and not hasattr(implementation, "run_commands")


def test_no_alternative_process_paths_or_stderr_heuristics_remain():
    with pytest.raises(ImportError):
        importlib.import_module("sandbox_manager.utils.classify_output")
    found = subprocess.run(["grep", "-rEn", r"run_commands?\(|classify_output|Traceback \(most recent|exit_code == 137",
                            "autograder", "web", "execution_host", "sandbox_manager", "github_action",
                            "--include=*.py"], cwd=ROOT, capture_output=True, text=True)
    assert found.stdout == ""


def test_preparation_and_every_execution_evaluator_use_run_process():
    session = MagicMock()
    session.run_process.return_value = exited("ok\n")
    session.read_artifact.side_effect = FileNotFoundError("absent")
    command = {"python": "python3 main.py"}
    definition = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
                  "preparation": {"languages": {"python": {"setup_commands": [
                      {"name": "setup", "command": "sh -c 'echo ready'"}]}}},
                  "criteria": {"base": {"weight": 100, "tests": [
                      {"id": "out", "type": "expect_output", "name": "out", "parameters": {
                          "program_command": command, "expected_output": "ok", "inputs": ["", "-n"]}},
                      {"id": "ok", "type": "dont_fail", "name": "ok", "parameters": {"program_command": "CMD"}},
                      {"id": "file", "type": "expect_file_artifact", "name": "file", "parameters": {
                          "program_command": "python3 main.py 'two words'", "artifact_path": "o.txt",
                          "expected_content": "x"}}]}}}
    outcome = build_pipeline(definition=definition, capabilities=HostCapabilities(execution=lambda _: session)).run(
        Submission("s", "s", "a", {"main.py": SubmissionFile("main.py", "")}, language=Language.PYTHON)).outcome
    assert outcome.status == "completed"
    requests = [call.args[0] for call in session.run_process.call_args_list]
    assert all(isinstance(request, ProcessRequest) for request in requests)
    assert [(request.argv, request.stdin) for request in requests] == [
        (("sh", "-c", "echo ready"), b""),
        (("python3", "main.py"), b"\n-n\n"),
        (("python3", "main.py"), b""),
        (("python3", "main.py", "two words"), b""),
    ]
    assert [test.score for test in outcome.tree.base.tests] == [100, 100, 0]


def test_dont_fail_sends_one_line_or_nothing():
    from autograder.template_library.input_output import DontFailTest
    from autograder.models.abstract.test_function import EvaluationInput
    for user_input, stdin in (("", b""), ("4", b"4\n"), ("-n", b"-n\n")):
        session = MagicMock()
        session.run_process.return_value = exited()
        DontFailTest().execute(EvaluationInput(language=Language.PYTHON, session=session),
                               program_command="python3 main.py", user_input=user_input)
        assert session.run_process.call_args.args[0].stdin == stdin


def test_returned_exit_and_status_reports():
    from autograder.template_library.input_output import DontFailTest
    from autograder.models.abstract.test_function import EvaluationInput
    session = MagicMock()
    for result, text in ((exited(code=1), "Exit code 1"), (exited(stderr="boom", code=3), "boom"),
                         (timed_out(duration=2), "timed out")):
        session.run_process.return_value = result
        report = DontFailTest().execute(EvaluationInput(language=Language.PYTHON, session=session),
                                        program_command="python3 main.py").report
        assert text in report, report


def test_definitions_reject_malformed_commands_at_compilation():
    from autograder import DefinitionValidationError, compile_definition
    base = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python", "java"]}
    for command, path in (("python3 'x", ["criteria", "base", "tests", 0, "parameters", "program_command"]),
                          ({"python": "python3 x", "java": 'java "Main'},
                           ["criteria", "base", "tests", 0, "parameters", "program_command", "java"])):
        value = dict(base, criteria={"base": {"weight": 100, "tests": [
            {"id": "t", "type": "dont_fail", "name": "t", "parameters": {"program_command": command}}]}})
        with pytest.raises(DefinitionValidationError) as failure:
            compile_definition(value)
        error = failure.value.errors()[0]
        assert error["code"] == "INVALID_COMMAND" and list(error["path"]) == path
    value = dict(base, languages=["python"], preparation={"languages": {"python": {"setup_commands": [
        {"name": "build", "command": "make 'all"}]}}},
        criteria={"base": {"weight": 100, "tests": [
            {"id": "t", "type": "dont_fail", "name": "t", "parameters": {"program_command": "CMD"}}]}})
    with pytest.raises(DefinitionValidationError):
        compile_definition(value)
