"""
Unit tests for SandboxContainer.extract_file.

Tests cover:
- Successful file extraction with UTF-8 content
- Successful extraction with latin-1 fallback
- Missing file (FileNotFoundError)
- Oversized file (ValueError)
- base64 command failure (RuntimeError)
- Non-regular path / exec_run failure (FileNotFoundError)
- exec_run raises exception (RuntimeError)
"""

import base64
import unittest
from unittest.mock import MagicMock, call

from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ExtractedFile


def _exec_run_result(exit_code: int, output: bytes) -> MagicMock:
    """Build a mock exec_run return value."""
    r = MagicMock()
    r.exit_code = exit_code
    r.output = output
    return r


class TestExtractFile(unittest.TestCase):
    """Tests for file extraction from sandbox containers."""

    def setUp(self):
        """Set up the test case with a mock container."""
        self.mock_container = MagicMock()
        self.mock_container.id = "abc123def456"
        self.sandbox = SandboxContainer(
            language=Language.PYTHON,
            container_ref=self.mock_container,
        )

    def test_success_utf8(self):
        """Successful extraction of a UTF-8 text file."""
        content = "comparacoes: 10\nmovimentacoes: 4\n"
        content_bytes = content.encode("utf-8")
        encoded = base64.b64encode(content_bytes)

        self.mock_container.exec_run.side_effect = [
            _exec_run_result(0, str(len(content_bytes)).encode()),
            _exec_run_result(0, encoded),
        ]

        result = self.sandbox.extract_file("/app/output.txt")

        self.assertIsInstance(result, ExtractedFile)
        self.assertEqual(result.path, "/app/output.txt")
        self.assertEqual(result.content_text, content)
        self.assertEqual(result.size, len(content_bytes))
        self.assertEqual(result.encoding, "utf-8")

    def test_success_latin1_fallback(self):
        """Falls back to latin-1 when content is not valid UTF-8."""
        content_bytes = b"\xe9\xe8\xea"  # latin-1 chars, invalid UTF-8
        encoded = base64.b64encode(content_bytes)

        self.mock_container.exec_run.side_effect = [
            _exec_run_result(0, str(len(content_bytes)).encode()),
            _exec_run_result(0, encoded),
        ]

        result = self.sandbox.extract_file("/app/data.bin")

        self.assertEqual(result.encoding, "latin-1")
        self.assertEqual(result.content_bytes, content_bytes)

    def test_file_not_found(self):
        """Raises FileNotFoundError when the stat check fails."""
        self.mock_container.exec_run.return_value = _exec_run_result(1, b"")

        with self.assertRaises(FileNotFoundError) as ctx:
            self.sandbox.extract_file("/app/missing.txt")

        self.assertIn("missing.txt", str(ctx.exception))

    def test_file_not_found_no_such(self):
        """Raises FileNotFoundError when stat returns non-zero exit code."""
        self.mock_container.exec_run.return_value = _exec_run_result(1, b"No such file or directory")

        with self.assertRaises(FileNotFoundError):
            self.sandbox.extract_file("/app/gone.txt")

    def test_oversized_file(self):
        """Raises ValueError when file exceeds max_bytes."""
        self.mock_container.exec_run.return_value = _exec_run_result(0, b"200")

        with self.assertRaises(ValueError) as ctx:
            self.sandbox.extract_file("/app/big.txt", max_bytes=100)

        self.assertIn("exceeds maximum size", str(ctx.exception))

    def test_base64_command_failure(self):
        """Raises RuntimeError when base64 read command fails."""
        content_bytes = b"hello"
        self.mock_container.exec_run.side_effect = [
            _exec_run_result(0, str(len(content_bytes)).encode()),
            _exec_run_result(1, b"permission denied"),
        ]

        with self.assertRaises(RuntimeError) as ctx:
            self.sandbox.extract_file("/app/file.txt")

        self.assertIn("Failed to read file", str(ctx.exception))

    def test_docker_api_generic_error(self):
        """Raises RuntimeError when exec_run raises an unexpected exception."""
        self.mock_container.exec_run.side_effect = Exception("Connection refused")

        with self.assertRaises(Exception):
            self.sandbox.extract_file("/app/file.txt")


if __name__ == "__main__":
    unittest.main()
