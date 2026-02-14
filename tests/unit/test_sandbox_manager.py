"""
Unit tests for SandboxContainer functionality.

Tests cover:
- File preparation with directory structure
- Single command execution
- Batch command execution (interactive stdin)
- Response object functionality
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, SandboxState, CommandResponse, HttpResponse
from autograder.models.dataclass.submission import SubmissionFile
import requests


class TestCommandResponse(unittest.TestCase):
    """Test the CommandResponse dataclass."""

    def test_command_response_creation(self):
        """Test creating a CommandResponse object."""
        response = CommandResponse(
            stdout="Hello World",
            stderr="",
            exit_code=0,
            execution_time=0.123
        )

        self.assertEqual(response.stdout, "Hello World")
        self.assertEqual(response.stderr, "")
        self.assertEqual(response.exit_code, 0)
        self.assertEqual(response.execution_time, 0.123)

    def test_output_property(self):
        """Test the output property for backward compatibility."""
        response = CommandResponse(
            stdout="Output",
            stderr="Error",
            exit_code=1,
            execution_time=0.5
        )

        self.assertEqual(response.output, "Output")
        self.assertEqual(str(response), "Output")


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


class TestSandboxContainer(unittest.TestCase):
    """Test SandboxContainer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_container = MagicMock()
        self.mock_container.id = "abc123def456"
        self.sandbox = SandboxContainer(
            language=Language.PYTHON,
            container_ref=self.mock_container,
            port=5000
        )

    def test_sandbox_initialization(self):
        """Test sandbox initializes with correct state."""
        self.assertEqual(self.sandbox.language, Language.PYTHON)
        self.assertEqual(self.sandbox.state, SandboxState.IDLE)
        self.assertEqual(self.sandbox.port, 5000)
        self.assertFalse(self.sandbox._workdir_prepared)

    def test_pickup_marks_busy(self):
        """Test pickup() changes state to BUSY."""
        self.sandbox.pickup()
        self.assertEqual(self.sandbox.state, SandboxState.BUSY)

    def test_release_marks_idle(self):
        """Test release() changes state to IDLE."""
        self.sandbox.pickup()
        self.sandbox.release()
        self.assertEqual(self.sandbox.state, SandboxState.IDLE)

    def test_prepare_workdir_with_simple_files(self):
        """Test preparing workdir with simple filenames."""
        submission_files = {
            "main.py": SubmissionFile("main.py", "print('Hello')"),
            "test.py": SubmissionFile("test.py", "import main")
        }

        self.mock_container.put_archive.return_value = True

        self.sandbox.prepare_workdir(submission_files)

        self.assertTrue(self.sandbox._workdir_prepared)
        self.mock_container.put_archive.assert_called_once()

        # Verify it was called with /app path
        call_args = self.mock_container.put_archive.call_args
        self.assertEqual(call_args[0][0], '/app')

    def test_prepare_workdir_with_nested_structure(self):
        """Test preparing workdir with nested directory structure."""
        submission_files = {
            "services/user_service.py": SubmissionFile(
                "services/user_service.py",
                "class UserService: pass"
            ),
            "models/user.py": SubmissionFile(
                "models/user.py",
                "class User: pass"
            ),
            "main.py": SubmissionFile("main.py", "from services import user_service")
        }

        self.mock_container.put_archive.return_value = True

        self.sandbox.prepare_workdir(submission_files)

        self.assertTrue(self.sandbox._workdir_prepared)
        self.mock_container.put_archive.assert_called_once()

    def test_prepare_workdir_empty_files(self):
        """Test preparing workdir with no files."""
        self.sandbox.prepare_workdir({})

        # Should not call put_archive for empty files
        self.mock_container.put_archive.assert_not_called()

    def test_run_command_success(self):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = (b"Hello World\n", b"")

        self.mock_container.exec_run.return_value = mock_result

        response = self.sandbox.run_command("echo 'Hello World'")

        self.assertIsInstance(response, CommandResponse)
        self.assertEqual(response.exit_code, 0)
        self.assertEqual(response.stdout.strip(), "Hello World")
        self.assertEqual(response.stderr, "")
        self.assertGreater(response.execution_time, 0)

    def test_run_command_with_stderr(self):
        """Test command execution with stderr output."""
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_result.output = (b"", b"Error occurred\n")

        self.mock_container.exec_run.return_value = mock_result

        response = self.sandbox.run_command("invalid_command")

        self.assertEqual(response.exit_code, 1)
        self.assertEqual(response.stdout, "")
        self.assertIn("Error occurred", response.stderr)

    def test_run_command_exception_handling(self):
        """Test command execution handles exceptions."""
        self.mock_container.exec_run.side_effect = Exception("Container crashed")

        response = self.sandbox.run_command("some_command")

        self.assertEqual(response.exit_code, -1)
        self.assertIn("Command execution failed", response.stderr)

    def test_run_commands_batch_input(self):
        """Test batch command execution with multiple inputs."""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = (b"30\n", b"")

        self.mock_container.exec_run.return_value = mock_result

        response = self.sandbox.run_commands(
            ["ADD", "10", "20"],
            program_command="python3 calculator.py"
        )

        self.assertEqual(response.exit_code, 0)
        self.assertIn("30", response.stdout)

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
        response = self.sandbox.make_request("POST", "/api/users", json_data=json_data)

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

