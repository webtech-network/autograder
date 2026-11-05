"""
Unit tests for SandboxContainer functionality.

Tests cover:
- File preparation with directory structure
- The process contract: argv/shell, exact stdin, exit status, bounded output
- Invalidation and artifact readback errors
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import base64

from autograder.models.process import ProcessRequest, ProcessStatus
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, ProcessExecutionError, SandboxInvalidatedError,
)
from sandbox_manager.sandbox_container import COLLECT, RUNNER, WRITE, SandboxContainer
from sandbox_manager.models.sandbox_models import SandboxState, HttpResponse
from autograder.models.language import Language
from tests.sandbox_profiles import TEST_IMAGES
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
                 run_error=None, hang=False):
        self.exit_code, self.stdout, self.stderr, self.marker = exit_code, stdout, stderr, marker
        self.survivors, self.run_error, self.hang = survivors, run_error, hang
        self.calls = []
        self.id, self.name = "abc123def456", "fake"

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
            def stream(name, data):
                return f"{name} {len(data)}\n".encode() + base64.b64encode(data[:int(cmd[5])]) + b"\n"
            return Mock(exit_code=0, output=f"survivors {self.survivors}\n".encode()
                        + stream("out", self.stdout) + stream("err", self.stderr))
        return Mock(exit_code=0, output=b"")


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

    def test_prepare_workdir_writes_each_file_with_exact_bytes(self):
        content = "print('ol\u00e1')\n" + "x" * 100_000  # larger than one argument chunk
        self.sandbox.prepare_workdir({"pkg/main.py": SubmissionFile("pkg/main.py", content)})
        written = b""
        for call in self.mock_container.exec_run.call_args_list:
            cmd = call.kwargs["cmd"]
            self.assertEqual(cmd[:3], ["/bin/sh", "-c", WRITE])
            self.assertEqual(cmd[4], "/app/pkg/main.py")
            written += base64.b64decode(cmd[6])
        self.assertEqual(written, content.encode("utf-8"))
        self.assertEqual([call.kwargs["cmd"][5] for call in self.mock_container.exec_run.call_args_list],
                         ["new", "append", "append"])

    def test_prepare_workdir_empty_files(self):
        self.sandbox.prepare_workdir({})
        self.mock_container.exec_run.assert_not_called()

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

    def test_container_stopped_under_the_process_keeps_its_exit_and_invalidates(self):
        container = ScriptedContainer(exit_code=137)
        container.exec_run_orig = container.exec_run

        def exec_run(cmd, **kwargs):
            if cmd[2] == COLLECT:
                raise OSError("container is not running")
            return container.exec_run_orig(cmd, **kwargs)
        container.exec_run, container.status, container.reload = exec_run, "exited", lambda: None
        sandbox = SandboxContainer(Language.PYTHON, container)
        result = sandbox.run_process(ProcessRequest(argv=("p",)))
        self.assertEqual((result.status, result.exit_code, result.stdout), (ProcessStatus.EXITED, 137, ""))
        with self.assertRaises(SandboxInvalidatedError):
            sandbox.run_process(ProcessRequest(argv=("p",)))
        container.status = "running"  # a live container whose readback failed is an execution error
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
        pool = LanguagePool(Language.PYTHON, config, client=None, budget=SandboxBudget(2))

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
        pool = LanguagePool(Language.JAVA, config, client=None, budget=SandboxBudget(2))

        name1 = pool._build_container_name()
        name2 = pool._build_container_name()
        assert name1.endswith("-0001")
        assert name2.endswith("-0002")
        # Same pool prefix
        assert name1[:-5] == name2[:-5]
