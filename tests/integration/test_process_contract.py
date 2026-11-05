"""One process contract in real containers, locally and through the real control API (ARC-08).

Every behavioural test runs against both backends: the local ``SandboxManager``
(also used by the Actions host) and a ``RemoteSandboxManager`` talking to the
private control API served by real uvicorn with its own real ``SandboxManager``.
"""
# Test names state each checked behaviour; some fixtures are requested only to
# parametrize the backend or keep a resource alive.
# pylint: disable=missing-function-docstring,unused-argument
import json
import socket
import threading
import time
from contextlib import contextmanager

import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessStatus, lines_to_stdin
from autograder.template_library import input_output
from execution_host.docker import DockerHost, DockerSession
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.errors import ArtifactReadError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.remote_client import RemoteSandboxManager, SandboxHandleGone
from tests.sandbox_profiles import TEST_IMAGES, sandbox_config
from tests.web.conftest import db_engine, session_factory  # pylint: disable=unused-import
from web.core.config import Settings
from web.main import create_app as create_web_app

TOKEN = "process-contract-token-0123456789"
BACKENDS = ("local", "remote")

PROBE = "import json, sys\nprint(json.dumps({'argv': sys.argv[1:], 'stdin': sys.stdin.buffer.read().hex()}))\n"
# Leaves a background writer behind and then blocks forever.
HANG = ("import os, time\n"
        "if os.fork() == 0:\n"
        "    while True:\n"
        "        open('/app/ticks', 'a').write('x'); time.sleep(0.05)\n"
        "while True: time.sleep(1)\n")
# Exits 0 after starting a daemon that would keep writing.
ORPHAN = ("import os, time\n"
          "if os.fork() == 0:\n"
          "    os.setsid()\n"
          "    while True:\n"
          "        open('/app/orphan', 'a').write('x'); time.sleep(0.05)\n")
# Fails unless it is the only live process besides the container's PID 1 and no writer is active.
CHECK = ("import os, sys, time\n"
         "def live():\n"
         "    found = []\n"
         "    for pid in filter(str.isdigit, os.listdir('/proc')):\n"
         "        try: state = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()[0]\n"
         "        except OSError: continue\n"
         "        if pid not in ('1', str(os.getpid())) and state != 'Z': found.append(pid)\n"
         "    return found\n"
         "def size(path): return os.path.getsize(path) if os.path.exists(path) else 0\n"
         "before = (size('/app/ticks'), size('/app/orphan')); time.sleep(0.5)\n"
         "after = (size('/app/ticks'), size('/app/orphan'))\n"
         "others = live()\n"
         "print(others, before, after)\n"
         "sys.exit(1 if others or before != after else 0)\n")
FILES = {"probe.py": PROBE, "hang.py": HANG, "orphan.py": ORPHAN, "check.py": CHECK,
         "fail.py": "import sys\nsys.exit(1)\n", "exit137.py": "import sys\nsys.exit(137)\n",
         "killed.py": "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n",
         "noisy.py": "import sys\nsys.stdout.write('x' * 5_000_000); sys.stderr.write('\\u00e9' * 1_000_000)\n",
         "hog.py": "import time\nblocks = []\nwhile True: blocks.append(bytearray(16 * 1024 * 1024)); time.sleep(0.01)\n",
         "artifact.py": "import os\nopen('secret.txt', 'w').write('hidden')\nos.chmod('secret.txt', 0)\n"}


def pool(**overrides):
    values = dict(language=Language.PYTHON, image=TEST_IMAGES[Language.PYTHON], pool_size=0, running_timeout=120)
    values.update(overrides)
    return SandboxPoolConfig(**values)


@contextmanager
def serve(app):
    """Serve the control API with real uvicorn on a free local port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=60)


@pytest.fixture(scope="module")
def managers():
    local = SandboxManager([pool()], max_sandboxes=4)
    settings = ControlSettings(token=TOKEN, reaper_interval_seconds=1)
    try:
        # The control service owns (and shuts down) its own real SandboxManager.
        with serve(create_app(settings, manager_factory=lambda: SandboxManager([pool()], max_sandboxes=4))) as url:
            remote = RemoteSandboxManager(url, TOKEN)
            yield {"local": local, "remote": remote}
            remote.shutdown()
    finally:
        local.shutdown()


@pytest.fixture(params=BACKENDS)
def session(request, managers):
    opened = DockerSession(managers[request.param], Language.PYTHON)
    try:
        opened.prepare_workdir({name: SubmissionFile(name, content) for name, content in FILES.items()})
        yield opened
    finally:
        opened.close()


def run(session, command=None, **options):
    request = ProcessRequest.command(command, **options) if command else ProcessRequest(**options)
    return session.run_process(request)


def probe(result):
    assert result.status is ProcessStatus.EXITED and result.exit_code == 0, result
    data = json.loads(result.stdout.splitlines()[0])
    return data["argv"], bytes.fromhex(data["stdin"])


# ----- stdin, arguments and shells agree on every backend --------------------------

STDIN_CASES = [
    ([], b""),                                   # empty stdin: immediate EOF, no newline
    ([""], b"\n"),                               # one empty line
    (["5", "3", "ADD"], b"5\n3\nADD\n"),         # multiple lines
    (["-n", "-e x"], b"-n\n-e x\n"),             # leading -n is data, never an echo option
    (["a\\nb", "C:\\dir\\"], b"a\\nb\nC:\\dir\\\n"),  # backslashes are literal
]


@pytest.mark.parametrize("lines,expected", STDIN_CASES)
def test_stdin_is_exact(session, lines, expected):
    assert probe(run(session, "python3 probe.py", stdin=lines_to_stdin(lines))) == ([], expected)


def test_raw_and_large_stdin_bytes_are_exact(session):
    raw = b"\x00\xff\r\n" + bytes(range(256)) * 400  # > 100 KiB: staged in chunks
    assert probe(run(session, "python3 probe.py", stdin=raw)) == ([], raw)


def test_quoted_arguments_follow_posix_splitting(session):
    argv, _ = probe(run(session, """python3 probe.py "a b" 'c d' e\\ f "" '$HOME' "*" """))
    assert argv == ["a b", "c d", "e f", "", "$HOME", "*"]


def test_shell_operators_are_arguments_without_an_explicit_shell(session):
    result = run(session, "python3 probe.py && echo injected > /app/pwned ; echo two")
    argv, _ = probe(result)
    assert argv == ["&&", "echo", "injected", ">", "/app/pwned", ";", "echo", "two"]
    assert result.stdout.count("\n") == 1
    with pytest.raises(FileNotFoundError):
        session.read_artifact("pwned")


def test_explicit_shell_runs_operators(session):
    result = run(session, shell="python3 probe.py one && echo two > /app/shell.txt; cat /app/shell.txt",
                 stdin=b"in\n")
    lines = result.stdout.splitlines()
    assert json.loads(lines[0]) == {"argv": ["one"], "stdin": b"in\n".hex()} and lines[1] == "two"


def test_malformed_quoting_never_reaches_a_backend(session):
    for command in ("python3 'unterminated", 'echo "open', "echo trailing\\"):
        with pytest.raises(ValueError, match="malformed quoting"):
            ProcessRequest.command(command)


# ----- exit status, not wording, classifies a process ------------------------------

def test_nonzero_exit_with_empty_stderr_is_a_returned_process(session):
    result = run(session, "python3 fail.py")
    assert (result.status, result.exit_code, result.stderr) == (ProcessStatus.EXITED, 1, "")


@pytest.mark.parametrize("program", ["exit137.py", "killed.py"])
def test_exit_137_is_reported_as_returned_not_as_a_timeout(session, program):
    result = run(session, f"python3 {program}", timeout=20)
    assert (result.status, result.exit_code) == (ProcessStatus.EXITED, 137)


def test_missing_executable_is_not_started(session):
    result = run(session, "./a.out")
    assert result.status is ProcessStatus.NOT_STARTED and result.missing_executable == "./a.out"
    # A shell that runs and reports 127 is an ordinary returned exit.
    assert run(session, shell="./a.out").exit_code == 127


# ----- deadlines terminate before the session is used again ------------------------

def test_timed_out_process_and_its_children_are_gone_before_the_next_process(session):
    result = run(session, "python3 hang.py", timeout=2)
    assert result.status is ProcessStatus.TIMED_OUT and result.exit_code is None
    check = run(session, "python3 check.py")
    assert check.exit_code == 0, check.stdout


def test_background_processes_do_not_outlive_their_run(session):
    assert run(session, "python3 orphan.py").exit_code == 0
    check = run(session, "python3 check.py")
    assert check.exit_code == 0, check.stdout


def test_memory_exhaustion_keeps_its_exit_and_never_fabricates_a_later_result(session):
    """Exhausting the memory limit is an exited, non-zero program.

    Whether the kernel kills only the process or the whole container depends on
    the host (cgroup/OOM configuration). Either way no later result is invented:
    a surviving sandbox runs the next process normally, and a stopped one is
    invalidated so every later operation raises a non-missing-file error.
    """
    result = run(session, "python3 hog.py", timeout=30)
    assert result.status is ProcessStatus.EXITED and result.exit_code != 0
    try:
        later = run(session, "python3 probe.py")
    except RuntimeError as error:
        assert not isinstance(error, FileNotFoundError)
    else:
        assert later.status is ProcessStatus.EXITED and later.exit_code == 0, later


# ----- bounded output and distinct readback failures -------------------------------

def test_output_is_bounded_by_the_executing_host(session):
    result = run(session, "python3 noisy.py", max_output_bytes=1024)
    assert result.exit_code == 0 and result.stdout_truncated and result.stderr_truncated
    assert result.stdout == "x" * 1024
    assert result.stderr == "\u00e9" * 512  # cut on a character boundary


def test_missing_artifact_failed_readback_and_unknown_handle_are_distinct(session, managers):
    with pytest.raises(FileNotFoundError):
        session.read_artifact("absent.txt")
    assert run(session, "python3 artifact.py").exit_code == 0
    with pytest.raises(ArtifactReadError) as unreadable:
        session.read_artifact("secret.txt")
    assert not isinstance(unreadable.value, FileNotFoundError)
    if isinstance(session.manager, RemoteSandboxManager):
        session.close()
        with pytest.raises(SandboxHandleGone) as closed:
            session.sandbox.extract_file("/app/absent.txt")
        assert not isinstance(closed.value, FileNotFoundError)


# ----- the real evaluator and preparation paths ------------------------------------

def grade(host, tests, files, preparation=None):
    definition = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
                  "criteria": {"base": {"weight": 100, "tests": tests}}}
    if preparation:
        definition["preparation"] = preparation
    pipeline = build_pipeline(definition=definition, capabilities=host.capabilities)
    return pipeline.run(Submission("s", "s", "a", {name: SubmissionFile(name, FILES[name]) for name in files},
                                   language=Language.PYTHON)).outcome


def dont_fail(test_id, command):
    return {"id": test_id, "type": "dont_fail", "name": test_id, "parameters": {"program_command": command}}


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("host") / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,)))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def test_exit_one_with_empty_stderr_is_an_assessed_zero(docker_host):
    outcome = grade(docker_host, [dont_fail("fails", "python3 fail.py"), dont_fail("runs", "python3 probe.py"),
                                  {"id": "killed", "type": "expect_output", "name": "killed",
                                   "parameters": {"program_command": "python3 killed.py", "expected_output": ""}}],
                    ["fail.py", "probe.py", "killed.py"])
    assert outcome.status == "completed", outcome.error
    scores = {test.id: test.score for test in outcome.tree.base.tests}
    assert scores == {"fails": 0, "runs": 100, "killed": 0}
    assert "1" in outcome.tree.base.tests[0].report and "timed out" not in outcome.tree.base.tests[2].report


def test_timeout_is_terminated_before_the_next_criterion_runs(docker_host, monkeypatch):
    monkeypatch.setattr(input_output, "RUN_TIMEOUT_SECONDS", 2)
    outcome = grade(docker_host, [dont_fail("hangs", "python3 hang.py"), dont_fail("alone", "python3 check.py")],
                    ["hang.py", "check.py"])
    assert outcome.status == "completed", outcome.error
    assert [(test.id, test.score) for test in outcome.tree.base.tests] == [("hangs", 0), ("alone", 100)]
    assert "timed out" in outcome.tree.base.tests[0].report


def test_memory_exhaustion_is_assessed_and_a_dead_sandbox_is_not_reused(docker_host):
    alone = grade(docker_host, [dont_fail("hog", "python3 hog.py")], ["hog.py"])
    assert alone.status == "completed" and alone.score == 0, alone.error
    # A later criterion either runs in a surviving container or, if the container
    # was taken down (host dependent), fails the grade: never a fabricated zero.
    after = grade(docker_host, [dont_fail("hog", "python3 hog.py"), dont_fail("next", "python3 probe.py")],
                  ["hog.py", "probe.py"])
    if after.status == "failed":
        assert after.error.code == "SANDBOX_ERROR" and after.score is None
    else:
        scores = {test.id: test.score for test in after.tree.base.tests}
        assert scores == {"hog": 0, "next": 100}, after


def test_program_that_cannot_start_is_not_an_assessed_zero(docker_host):
    outcome = grade(docker_host, [dont_fail("missing", "./a.out")], ["probe.py"])
    assert outcome.status == "failed" and outcome.error.code == "PROCESS_START_FAILED" and outcome.score is None


def test_preparation_uses_the_same_process_contract(docker_host):
    preparation = {"languages": {"python": {"setup_commands": [
        {"name": "explicit shell", "command": "sh -c 'echo prepared > ready.txt'"},
        {"name": "argv", "command": "python3 probe.py && false"}]}}}
    tests = [{"id": "ready", "type": "expect_file_artifact", "name": "ready", "parameters": {
        "program_command": "python3 probe.py", "artifact_path": "ready.txt", "expected_content": "prepared"}}]
    outcome = grade(docker_host, tests, ["probe.py"], preparation)
    assert outcome.status == "completed" and outcome.score == 100, outcome.error
    failing = {"languages": {"python": {"setup_commands": [{"name": "fails", "command": "python3 fail.py"}]}}}
    outcome = grade(docker_host, tests, ["probe.py", "fail.py"], failing)
    assert outcome.status == "failed" and outcome.error.code == "PREPARATION_FAILED"


def test_artifact_evaluator_distinguishes_missing_from_unreadable(docker_host):
    def artifact(path):
        return [{"id": "artifact", "type": "expect_file_artifact", "name": "artifact", "parameters": {
            "program_command": "python3 artifact.py", "artifact_path": path, "expected_content": "hidden"}}]
    missing = grade(docker_host, artifact("absent.txt"), ["artifact.py"])
    assert missing.status == "completed" and missing.score == 0
    unreadable = grade(docker_host, artifact("secret.txt"), ["artifact.py"])
    assert unreadable.status == "failed" and unreadable.error.code == "SANDBOX_ERROR"


# ----- HTTP: grading and deliberate execution keep their own policies --------------

@pytest.fixture
async def web_application(session_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "process-token")
    config = tmp_path / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,)))
    owner = DockerHost(mode="local", config_file=str(config))
    app = create_web_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts")), session_factory=session_factory,
                         capabilities=owner.capabilities, resource_owner=owner, start_workers=False)
    await app.state.host.start()
    yield app
    await app.state.host.close()


@pytest.mark.asyncio
async def test_http_grading_assesses_a_silent_failure_and_rejects_malformed_commands(web_application):
    headers = {"Authorization": "Bearer process-token"}
    async with AsyncClient(transport=ASGITransport(app=web_application), base_url="http://test",
                           headers=headers) as client:
        bad = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
               "criteria": {"base": {"weight": 100, "tests": [dont_fail("bad", "python3 'main.py")]}}}
        rejected = await client.post("/api/v1/configs", json={"external_assignment_id": "bad", "definition": bad})
        assert rejected.status_code == 422 and rejected.json()["detail"][0]["code"] == "INVALID_COMMAND"
        bad_setup = dict(bad, criteria={"base": {"weight": 100, "tests": [dont_fail("ok", "python3 fail.py")]}},
                         preparation={"languages": {"python": {"setup_commands": [
                             {"name": "x", "command": "make 'all"}]}}})
        rejected = await client.post("/api/v1/configs", json={"external_assignment_id": "bad2", "definition": bad_setup})
        assert rejected.status_code == 422

        good = dict(bad, criteria={"base": {"weight": 100, "tests": [dont_fail("silent", "python3 fail.py")]}})
        assert (await client.post("/api/v1/configs", json={"external_assignment_id": "silent",
                                                           "definition": good})).status_code == 200
        accepted = await client.post("/api/v1/submissions", json={
            "external_assignment_id": "silent", "external_user_id": "u", "username": "u", "language": "python",
            "files": [{"filename": "fail.py", "content": FILES["fail.py"]}]})
        assert accepted.status_code == 202
        assert await web_application.state.host.worker.run_once()
        details = (await client.get(f"{accepted.headers['Location']}/details")).json()
        assert details["status"] == "completed" and details["final_score"] == 0, details
        assert details["outcome"]["tree"]["base"]["tests"][0]["score"] == 0


@pytest.mark.asyncio
async def test_deliberate_execution_uses_exact_stdin_and_stops_on_timeout(web_application, monkeypatch):
    from web.service import deliberate_execution_service
    monkeypatch.setattr(deliberate_execution_service, "CASE_TIMEOUT_SECONDS", 2)
    files = [{"filename": name, "content": FILES[name]} for name in ("probe.py", "hang.py", "check.py", "fail.py")]
    async with AsyncClient(transport=ASGITransport(app=web_application), base_url="http://test",
                           headers={"Authorization": "Bearer process-token"}) as client:
        response = await client.post("/api/v1/execute", json={
            "language": "python", "submission_files": files, "program_command": "python3 probe.py '-n'",
            "test_cases": [[""], ["-n", "a\\b"], ["x"]]})
        assert response.status_code == 200, response.text
        stdins = [bytes.fromhex(json.loads(item["stdout"])["stdin"]) for item in response.json()["results"]]
        assert stdins == [b"\n", b"-n\na\\b\n", b"x\n"]
        assert json.loads(response.json()["results"][0]["stdout"])["argv"] == ["-n"]

        omitted = await client.post("/api/v1/execute", json={
            "language": "python", "submission_files": files, "program_command": "python3 probe.py"})
        assert bytes.fromhex(json.loads(omitted.json()["results"][0]["stdout"])["stdin"]) == b""

        failed = await client.post("/api/v1/execute", json={
            "language": "python", "submission_files": files, "program_command": "python3 fail.py"})
        result = failed.json()["results"][0]
        assert failed.status_code == 200 and (result["category"], result["exit_code"]) == ("runtime_error", 1)

        timed = await client.post("/api/v1/execute", json={
            "language": "python", "submission_files": files, "program_command": "python3 hang.py",
            "test_cases": [["a"], ["b"]]})
        body = timed.json()
        assert timed.status_code == 200 and body["stopped_early"] is True
        assert [item["category"] for item in body["results"]] == ["timeout"]
