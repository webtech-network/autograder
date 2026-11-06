"""
Unit tests for SandboxContainer functionality.

Tests cover:
- File preparation with directory structure
- The process contract: argv/shell, exact stdin, exit status, bounded output
- Invalidation and artifact readback errors
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
import base64

import docker
import pytest
import requests as http

from autograder.models.process import ProcessRequest, ProcessStatus, SandboxExhausted
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, ProcessExecutionError, SandboxInvalidatedError,
)
from sandbox_manager.sandbox_container import COLLECT, READ, RUNNER, STAGE, SandboxContainer, _demultiplex
from sandbox_manager.models.sandbox_models import SandboxState, HttpResponse
from autograder.models.language import Language
from tests.docker_exec_double import StdinExecApi
from tests.sandbox_profiles import TEST_IMAGES
from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.dataclass.submission import SubmissionFile
import requests


class TestHttpResponse(unittest.TestCase):
    """Test the HttpResponse wrapper."""

    def test_http_response_wrapper(self):
        """Test HttpResponse wraps requests.Response correctly."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"status": "success"}
        mock_response.ok = True

        http_response = HttpResponse(mock_response)

        self.assertEqual(http_response.status_code, 200)
        self.assertEqual(http_response.text, "OK")
        self.assertEqual(http_response.headers["Content-Type"], "application/json")
        self.assertEqual(http_response.json(), {"status": "success"})
        self.assertTrue(http_response.ok)


class ScriptedContainer:
    """A docker container double that answers the sandbox's fixed scripts."""

    def __init__(self, exit_code=0, stdout=b"", stderr=b"", marker=b"autograder:started\n", survivors=0,
                 run_error=None, hang=False, limits=(0, 0), collect_error=None, state=None, wait_error=None,
                 unstartable_collects=0, pids=None):
        self.exit_code, self.stdout, self.stderr, self.marker = exit_code, stdout, stderr, marker
        self.survivors, self.run_error, self.hang = survivors, run_error, hang
        self.limits, self.collect_error, self.wait_error = limits, collect_error, wait_error
        # runc refuses to start this many collector execs (no pid left), as Docker reports it.
        self.unstartable_collects = unstartable_collects
        # Docker's pids_stats of the running container.
        self.pids = pids or {"current": 5, "limit": 64}
        # Docker's record of the container (``State``), consulted only when a control exec fails.
        self.attrs = {"State": state or {"Status": "running", "Running": True, "OOMKilled": False, "ExitCode": 0}}
        self.calls = []
        # Staging execs, fed on stdin, go through Docker's low-level exec API.
        self.client = SimpleNamespace(api=StdinExecApi(self.calls))
        self.waited = 0
        self.id, self.name = "abc123def456", "fake"

    def wait(self, timeout=None):
        self.waited += 1
        if self.wait_error:
            raise self.wait_error
        return {"StatusCode": self.attrs["State"]["ExitCode"]}

    def stats(self, stream=True, one_shot=False):
        assert stream is False and one_shot is True
        return {"pids_stats": self.pids}

    def reload(self):
        if isinstance(self.wait_error, docker.errors.NotFound):
            raise self.wait_error

    def exec_run(self, cmd, user=None, workdir=None, **kwargs):
        self.calls.append((cmd, user, workdir))
        script = cmd[2] if cmd[:2] == ["/bin/sh", "-c"] else None
        if script == RUNNER:
            if self.run_error:
                raise self.run_error
            if self.hang:
                import time
                time.sleep(2)
            return Mock(exit_code=self.exit_code, output=self.marker)
        if script == COLLECT:
            if self.collect_error:
                raise self.collect_error
            if self.unstartable_collects:
                self.unstartable_collects -= 1
                return Mock(exit_code=128, output=b"OCI runtime exec failed: exec failed: unable to start container "
                                                  b"process: nsexec-0: unable to spawn stage-1: Resource temporarily "
                                                  b"unavailable\r\n")

            def stream(name, data):
                return f"{name} {len(data)}\n".encode() + base64.b64encode(data[:int(cmd[5])]) + b"\n"
            header = f"survivors {self.survivors}\nlimits {self.limits[0]} {self.limits[1]}\n".encode()
            return Mock(exit_code=0, output=header + stream("out", self.stdout) + stream("err", self.stderr))
        return Mock(exit_code=0, output=b"")


# ----- who ended the run: host-side evidence, never an exit code (COR-01) -------------

STOPPED = {"Status": "exited", "Running": False}


def _run(container, state=SandboxState.ACTIVE):
    sandbox = SandboxContainer(Language.PYTHON, container)
    sandbox.state = state
    try:
        return sandbox, sandbox.run_process(ProcessRequest(argv=("python3", "main.py")))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return sandbox, exc


@pytest.mark.parametrize("container, state, outcome", [
    # The container's cgroup recorded the limit while it kept running (runc).
    (ScriptedContainer(exit_code=137, limits=(1, 0)), SandboxState.ACTIVE, SandboxExhausted),
    (ScriptedContainer(hang=True, survivors=3, limits=(0, 12)), SandboxState.ACTIVE, SandboxExhausted),
    # runc found no pid to start the collector at first; a later start reads the limit.
    (ScriptedContainer(hang=True, unstartable_collects=3, limits=(0, 40)), SandboxState.ACTIVE, SandboxExhausted),
    # runc never found a pid for it, and Docker reports the running container at its pids limit.
    (ScriptedContainer(hang=True, unstartable_collects=99, pids={"current": 64, "limit": 64},
                       wait_error=http.ReadTimeout("still running")), SandboxState.ACTIVE, SandboxExhausted),
    # The container stopped by itself under the submission: OOM, or the runtime (gVisor) could not continue.
    (ScriptedContainer(exit_code=128, collect_error=OSError("not running"),
                       state={**STOPPED, "OOMKilled": True, "ExitCode": 137}), SandboxState.ACTIVE, SandboxExhausted),
    (ScriptedContainer(exit_code=128, collect_error=OSError("not running"),
                       state={**STOPPED, "OOMKilled": False, "ExitCode": 2}), SandboxState.ACTIVE, SandboxExhausted),
    # The host ended it: pool disposal (reaper, shutdown), removal, a signal to PID 1, or no answer.
    (ScriptedContainer(exit_code=137, collect_error=OSError("not running"),
                       state={**STOPPED, "OOMKilled": True, "ExitCode": 137}), SandboxState.CLOSING, ProcessExecutionError),
    (ScriptedContainer(exit_code=137, collect_error=OSError("gone"), wait_error=docker.errors.NotFound("gone")),
     SandboxState.ACTIVE, ProcessExecutionError),
    (ScriptedContainer(exit_code=137, collect_error=OSError("not running"),
                       state={**STOPPED, "OOMKilled": False, "ExitCode": 137}), SandboxState.ACTIVE, ProcessExecutionError),
    (ScriptedContainer(exit_code=137, collect_error=OSError("not running"),
                       state={**STOPPED, "OOMKilled": False, "ExitCode": 143}), SandboxState.ACTIVE, ProcessExecutionError),
    (ScriptedContainer(collect_error=OSError("daemon error"), wait_error=http.ReadTimeout("still running")),
     SandboxState.ACTIVE, ProcessExecutionError),
    # A control exec that keeps failing to start below the pids limit is the host's fault.
    (ScriptedContainer(unstartable_collects=99, wait_error=http.ReadTimeout("still running")),
     SandboxState.ACTIVE, ProcessExecutionError),
], ids=["cgroup-memory-limit", "cgroup-refused-fork", "collector-started-on-retry", "running-at-pids-limit",
        "stopped-oom", "runtime-stopped-itself", "pool-disposed",
        "removed", "docker-kill", "docker-stop", "running-control-failed", "control-unstartable-below-limit"])
def test_who_ended_the_run_is_decided_from_host_evidence(container, state, outcome):
    sandbox, raised = _run(container, state)
    assert type(raised) is outcome, raised  # pylint: disable=unidiomatic-typecheck
    if outcome is SandboxExhausted:
        assert sandbox.exhausted and not isinstance(raised, RuntimeError)
        for later in (lambda: sandbox.run_process(ProcessRequest(argv=("p",))),
                      lambda: sandbox.extract_file("/app/out.txt"),
                      lambda: sandbox.prepare_workdir({"a.py": SubmissionFile("a.py", "")})):
            with pytest.raises(SandboxExhausted):
                later()
    else:
        assert not sandbox.exhausted and sandbox.invalidated is not None
        with pytest.raises(SandboxInvalidatedError):
            sandbox.run_process(ProcessRequest(argv=("p",)))
    if state is not SandboxState.ACTIVE:
        assert container.waited == 0  # the pool's own disposal record decides first


def test_an_exit_code_alone_never_decides():
    """137 with no limit recorded and a running container is the program's own exit."""
    sandbox, result = _run(ScriptedContainer(exit_code=137))
    assert (result.status, result.exit_code) == (ProcessStatus.EXITED, 137)
    assert not sandbox.exhausted and sandbox.invalidated is None


def test_control_execs_run_as_root_and_the_submission_as_sandbox():
    container = ScriptedContainer()
    sandbox = SandboxContainer(Language.PYTHON, container)
    sandbox.prepare_workdir({"a.py": SubmissionFile("a.py", "x")})
    sandbox.run_process(ProcessRequest(argv=("p",), stdin=b"x" * 60_000))
    with pytest.raises(ArtifactReadError):  # the double answers READ with nothing
        sandbox.extract_file("/app/a.py")
    users = [(call[0][2] if call[0][:2] == ["/bin/sh", "-c"] else call[0], call[1]) for call in container.calls]
    assert users == [(STAGE, "sandbox"), (STAGE, "sandbox"), (RUNNER, "sandbox"), (COLLECT, "root"), (READ, "root")]


class TestSandboxContainer(unittest.TestCase):
    """Test SandboxContainer functionality."""

    def setUp(self):
        self.mock_container = MagicMock()
        self.mock_container.id = "abc123def456"
        self.mock_container.exec_run.return_value = Mock(exit_code=0, output=b"")
        self.sandbox = SandboxContainer(language=Language.PYTHON, container_ref=self.mock_container, port=5000)

    def test_sandbox_initialization(self):
        self.assertEqual(self.sandbox.language, Language.PYTHON)
        self.assertEqual(self.sandbox.state, SandboxState.IDLE)
        self.assertEqual(self.sandbox.port, 5000)
        self.assertIsNone(self.sandbox.invalidated)

    def test_activate_marks_active(self):
        """A sandbox is activated once; it is never returned to idle."""
        self.sandbox.activate()
        self.assertEqual(self.sandbox.state, SandboxState.ACTIVE)
        self.assertIsNotNone(self.sandbox.activated_at)
        self.assertFalse(hasattr(self.sandbox, "release"))

    def test_prepare_workdir_stages_every_file_in_one_transfer(self):
        container = ScriptedContainer()
        content = "print('ol\u00e1')\n" + "x" * 100_000
        files = {"pkg/main.py": content, "\u00e9t\u00e9/\u6587.py": "", **{f"m{i}.py": str(i) for i in range(98)}}
        SandboxContainer(Language.PYTHON, container).prepare_workdir(
            {name: SubmissionFile(name, text) for name, text in files.items()})
        self.assertEqual(container.calls, [(STAGE, "sandbox", "/")])
        [staged] = container.client.api.archives()
        self.assertEqual(staged, {f"app/{name}": (text.encode("utf-8"), 0o644) for name, text in files.items()})

    def test_prepare_workdir_empty_files(self):
        self.sandbox.prepare_workdir({})
        self.mock_container.exec_run.assert_not_called()
        self.mock_container.client.api.exec_create.assert_not_called()

    def test_prepare_workdir_validates_every_path_before_transferring_any(self):
        container = ScriptedContainer()
        for bad in ("../escape.py", "/etc/passwd", "a/../../b.py", ".."):
            with self.subTest(path=bad), self.assertRaises(RuntimeError) as raised:
                SandboxContainer(Language.PYTHON, container).prepare_workdir(
                    {"ok.py": SubmissionFile("ok.py", "x"), bad: SubmissionFile(bad, "x")})
            self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertEqual(container.calls, [])

    def test_a_failed_transfer_invalidates_the_sandbox(self):
        container = ScriptedContainer()
        container.client.api.exit_code, container.client.api.output = 2, b"tar: write error: No space left\n"
        sandbox = SandboxContainer(Language.PYTHON, container)
        with self.assertRaises(RuntimeError) as raised:
            sandbox.prepare_workdir({"a.py": SubmissionFile("a.py", "x")})
        self.assertIsInstance(raised.exception.__cause__, ProcessExecutionError)
        self.assertIn("No space left", str(raised.exception))
        with self.assertRaises(SandboxInvalidatedError):
            sandbox.run_process(ProcessRequest(argv=("p",)))

    def test_an_unfinished_exec_is_not_a_success(self):
        container = ScriptedContainer()
        container.client.api.exit_code = None  # Docker has no exit code for it
        sandbox = SandboxContainer(Language.PYTHON, container)
        with self.assertRaises(ProcessExecutionError):
            sandbox.inject_assets([ResolvedAsset("/tmp/a", b"x")])
        self.assertIsNotNone(sandbox.invalidated)

    def test_a_docker_daemon_over_tls_is_refused_before_any_exec(self):
        """A TLS socket cannot be half-closed, so stdin could never end: refuse, never guess."""
        container = ScriptedContainer()
        container.client.api.base_url = "https://docker.example:2376"
        sandbox = SandboxContainer(Language.PYTHON, container)
        with self.assertRaises(ProcessExecutionError) as raised:
            sandbox.inject_assets([ResolvedAsset("/tmp/a", b"x")])
        self.assertIn("not TLS", str(raised.exception))
        self.assertEqual(container.calls, [])
        self.assertIsNotNone(sandbox.invalidated)

    def test_stdin_up_to_the_inline_size_is_an_argument_and_above_it_one_transfer(self):
        for size, staged in ((48 * 1024, False), (48 * 1024 + 1, True), (1024 * 1024, True)):
            with self.subTest(size=size):
                container = ScriptedContainer()
                stdin = bytes(range(256)) * (size // 256) + b"\x00" * (size % 256)
                SandboxContainer(Language.PYTHON, container).run_process(ProcessRequest(argv=("p",), stdin=stdin))
                scripts = [call[0] if call[0] == STAGE else call[0][2] for call in container.calls]
                runner = next(call[0] for call in container.calls if call[0][2:3] == [RUNNER])
                if staged:
                    [archive] = container.client.api.archives()
                    [(name, (data, _))] = archive.items()
                    self.assertEqual((name, runner[5]), (f"{runner[4][1:]}/in", "-"))
                    self.assertEqual(data, stdin)
                    self.assertEqual(scripts, [STAGE, RUNNER, COLLECT])
                else:
                    self.assertEqual(base64.b64decode(runner[5]), stdin)
                    self.assertEqual(scripts, [RUNNER, COLLECT])

    def test_docker_stream_frames_are_joined(self):
        frames = b"".join(bytes([kind, 0, 0, 0]) + len(data).to_bytes(4, "big") + data
                          for kind, data in ((1, b"out "), (2, b"err"), (1, b"")))
        self.assertEqual(_demultiplex(frames), b"out err")

    def test_argv_is_passed_as_positional_parameters_never_as_shell_text(self):
        container = ScriptedContainer(stdout=b"ok\n")
        sandbox = SandboxContainer(Language.PYTHON, container)
        result = sandbox.run_process(ProcessRequest.command('python3 "my script.py" ) && touch /tmp/pwned',
                                                            stdin=b"-n\n"))
        cmd, user, workdir = container.calls[0]
        self.assertEqual(cmd[:4], ["/bin/sh", "-c", RUNNER, "autograder-run"])
        self.assertEqual(base64.b64decode(cmd[5]), b"-n\n")
        self.assertEqual(cmd[6:], ["python3", "my script.py", ")", "&&", "touch", "/tmp/pwned"])
        self.assertEqual((user, workdir), ("sandbox", "/app"))
        self.assertEqual((result.status, result.exit_code, result.stdout), (ProcessStatus.EXITED, 0, "ok\n"))

    def test_explicit_shell_is_the_only_shell(self):
        container = ScriptedContainer()
        SandboxContainer(Language.PYTHON, container).run_process(ProcessRequest(shell="echo one && echo two"))
        self.assertEqual(container.calls[0][0][6:], ["/bin/sh", "-c", "echo one && echo two"])

    def test_nonzero_exit_with_empty_stderr_is_a_returned_process(self):
        result = SandboxContainer(Language.PYTHON, ScriptedContainer(exit_code=1)).run_process(
            ProcessRequest(argv=("python3", "main.py")))
        self.assertEqual((result.status, result.exit_code, result.stderr), (ProcessStatus.EXITED, 1, ""))

    def test_exit_137_is_reported_as_returned_not_as_timeout(self):
        result = SandboxContainer(Language.PYTHON, ScriptedContainer(exit_code=137)).run_process(
            ProcessRequest(argv=("python3", "main.py")))
        self.assertEqual((result.status, result.exit_code), (ProcessStatus.EXITED, 137))

    def test_missing_executable_is_not_started(self):
        container = ScriptedContainer(exit_code=127, marker=b"autograder:not-found\n")
        result = SandboxContainer(Language.PYTHON, container).run_process(ProcessRequest(argv=("./a.out",)))
        self.assertEqual((result.status, result.missing_executable), (ProcessStatus.NOT_STARTED, "./a.out"))

    def test_output_is_bounded_at_readback(self):
        container = ScriptedContainer(stdout=b"x" * 100, stderr="\u00e9".encode() * 10)
        result = SandboxContainer(Language.PYTHON, container).run_process(
            ProcessRequest(argv=("p",), max_output_bytes=5))
        self.assertEqual((result.stdout, result.stdout_truncated), ("xxxxx", True))
        self.assertEqual((result.stderr, result.stderr_truncated), ("\u00e9\u00e9", True))  # no split character

    def test_exec_failure_raises_and_invalidates(self):
        sandbox = SandboxContainer(Language.PYTHON, ScriptedContainer(run_error=OSError("container crashed")))
        with self.assertRaises(ProcessExecutionError):
            sandbox.run_process(ProcessRequest(argv=("p",)))
        with self.assertRaises(SandboxInvalidatedError):
            sandbox.run_process(ProcessRequest(argv=("p",)))
        with self.assertRaises(SandboxInvalidatedError):
            sandbox.extract_file("/app/out.txt")

    def test_unconfirmed_termination_invalidates_the_sandbox(self):
        sandbox = SandboxContainer(Language.PYTHON, ScriptedContainer(survivors=1))
        with self.assertRaises(ProcessExecutionError):
            sandbox.run_process(ProcessRequest(argv=("p",)))
        self.assertIsNotNone(sandbox.invalidated)

    def test_timeout_collects_before_returning(self):
        container = ScriptedContainer(hang=True, stdout=b"partial")
        result = SandboxContainer(Language.PYTHON, container).run_process(ProcessRequest(argv=("p",), timeout=0.2))
        self.assertEqual((result.status, result.exit_code, result.stdout), (ProcessStatus.TIMED_OUT, None, "partial"))
        self.assertEqual([call[0][2] for call in container.calls], [RUNNER, COLLECT])

    def test_unparseable_readback_is_an_execution_error(self):
        container = ScriptedContainer()
        container.exec_run = lambda cmd, **kwargs: Mock(exit_code=0, output=b"autograder:started\n" if cmd[2] == RUNNER else b"garbage")
        with self.assertRaises(ProcessExecutionError):
            SandboxContainer(Language.PYTHON, container).run_process(ProcessRequest(argv=("p",)))

    def test_artifact_missing_vs_unreadable(self):
        self.mock_container.exec_run.return_value = Mock(exit_code=3, output=b"")
        with self.assertRaises(FileNotFoundError):
            self.sandbox.extract_file("/app/out.txt")
        self.mock_container.exec_run.return_value = Mock(exit_code=1, output=b"head: I/O error")
        with self.assertRaises(ArtifactReadError) as unreadable:
            self.sandbox.extract_file("/app/out.txt")
        self.assertNotIsInstance(unreadable.exception, FileNotFoundError)
        self.mock_container.exec_run.return_value = Mock(exit_code=0, output=b"11\n" + base64.b64encode(b"x" * 11))
        with self.assertRaises(ArtifactTooLargeError):
            self.sandbox.extract_file("/app/out.txt", max_bytes=10)
        self.mock_container.exec_run.return_value = Mock(exit_code=0, output=b"2\n" + base64.b64encode(b"ok"))
        self.assertEqual(self.sandbox.extract_file("/app/out.txt").content_text, "ok")

    @patch('sandbox_manager.sandbox_container.requests')
    def test_make_request_get(self, mock_requests):
        """Test making GET request to container."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_requests.get.return_value = mock_response

        response = self.sandbox.make_request("GET", "/health")

        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)
        mock_requests.get.assert_called_once()

    @patch('sandbox_manager.sandbox_container.requests')
    def test_make_request_post_json(self, mock_requests):
        """Test making POST request with JSON data."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 201
        mock_requests.post.return_value = mock_response

        json_data = {"name": "John", "email": "john@example.com"}
        response = self.sandbox.make_request("POST", "/api/users", json=json_data)

        self.assertEqual(response.status_code, 201)
        mock_requests.post.assert_called_once()

        # Verify json parameter was used
        call_kwargs = mock_requests.post.call_args[1]
        self.assertEqual(call_kwargs['json'], json_data)

    def test_make_request_no_port(self):
        """Test make_request raises error when port is not configured."""
        sandbox_no_port = SandboxContainer(
            language=Language.PYTHON,
            container_ref=self.mock_container,
            port=None
        )

        with self.assertRaises(ValueError) as context:
            sandbox_no_port.make_request("GET", "/health")

        self.assertIn("port not configured", str(context.exception))


if __name__ == '__main__':
    unittest.main()


class TestLanguagePoolNaming(unittest.TestCase):
    """Test deterministic container naming in LanguagePool."""

    def test_build_container_name_format(self):
        """Test that _build_container_name produces ag-sbx-{lang}-{pool8}-{seq4}."""
        import re
        from sandbox_manager.language_pool import LanguagePool, SandboxBudget
        from sandbox_manager.models.pool_config import SandboxPoolConfig

        config = SandboxPoolConfig(
            language=Language.PYTHON,
            image=TEST_IMAGES[Language.PYTHON],
            pool_size=1,
            running_timeout=60
        )
        pool = LanguagePool(Language.PYTHON, config, client=None, runtime="runc", budget=SandboxBudget(2))

        name = pool._build_container_name()
        assert re.match(r'^ag-sbx-python-[a-f0-9]{8}-0001$', name), f"Unexpected name: {name}"

    def test_build_container_name_increments(self):
        """Test that sequential calls produce incrementing sequence numbers."""
        from sandbox_manager.language_pool import LanguagePool, SandboxBudget
        from sandbox_manager.models.pool_config import SandboxPoolConfig

        config = SandboxPoolConfig(
            language=Language.JAVA,
            image=TEST_IMAGES[Language.JAVA],
            pool_size=1,
            running_timeout=60
        )
        pool = LanguagePool(Language.JAVA, config, client=None, runtime="runc", budget=SandboxBudget(2))

        name1 = pool._build_container_name()
        name2 = pool._build_container_name()
        assert name1.endswith("-0001")
        assert name2.endswith("-0002")
        # Same pool prefix
        assert name1[:-5] == name2[:-5]
