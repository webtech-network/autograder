"""
Unit tests for SandboxContainer.extract_file.

One bounded exec reads a regular file back. The outcomes stay distinct:
missing file (FileNotFoundError), too large (ArtifactTooLargeError), an
existing file that could not be read (ArtifactReadError), and an exec that
failed (ArtifactReadError; the sandbox is invalidated).
"""

import base64
import unittest
from unittest.mock import MagicMock

from sandbox_manager.errors import ArtifactReadError, ArtifactTooLargeError
from sandbox_manager.sandbox_container import READ, SandboxContainer
from autograder.models.execution import ExtractedFile
from autograder.models.language import Language


def _exec_run_result(exit_code: int, output: bytes) -> MagicMock:
    """Build a mock exec_run return value."""
    r = MagicMock()
    r.exit_code = exit_code
    r.output = output
    return r


def _found(content: bytes, size=None) -> MagicMock:
    return _exec_run_result(0, str(len(content) if size is None else size).encode() + b"\n" + base64.b64encode(content))


class TestExtractFile(unittest.TestCase):
    """Tests for file extraction from sandbox containers."""

    def setUp(self):
        self.mock_container = MagicMock()
        self.mock_container.id = "abc123def456"
        self.sandbox = SandboxContainer(language=Language.PYTHON, container_ref=self.mock_container)

    def test_success_utf8(self):
        content = "comparacoes: 10\nmovimentacoes: 4\n"
        self.mock_container.exec_run.return_value = _found(content.encode("utf-8"))
        result = self.sandbox.extract_file("/app/output.txt")
        self.assertIsInstance(result, ExtractedFile)
        self.assertEqual((result.path, result.content_text, result.encoding), ("/app/output.txt", content, "utf-8"))
        self.assertEqual(result.size, len(content.encode("utf-8")))

    def test_success_latin1_fallback(self):
        content_bytes = b"\xe9\xe8\xea"
        self.mock_container.exec_run.return_value = _found(content_bytes)
        result = self.sandbox.extract_file("/app/data.bin")
        self.assertEqual((result.encoding, result.content_bytes), ("latin-1", content_bytes))

    def test_empty_file(self):
        self.mock_container.exec_run.return_value = _found(b"")
        self.assertEqual(self.sandbox.extract_file("/app/empty.txt").content_bytes, b"")

    def test_file_not_found(self):
        self.mock_container.exec_run.return_value = _exec_run_result(3, b"")
        with self.assertRaises(FileNotFoundError) as ctx:
            self.sandbox.extract_file("/app/missing.txt")
        self.assertIn("missing.txt", str(ctx.exception))

    def test_oversized_file(self):
        self.mock_container.exec_run.return_value = _found(b"x" * 101, size=200)
        with self.assertRaises(ArtifactTooLargeError) as ctx:
            self.sandbox.extract_file("/app/big.txt", max_bytes=100)
        self.assertIn("exceeds maximum size", str(ctx.exception))
        # The readback itself is bounded to max_bytes + 1.
        self.assertEqual(self.mock_container.exec_run.call_args.kwargs["cmd"][5], "101")

    def test_file_that_grows_past_the_limit_is_too_large(self):
        self.mock_container.exec_run.return_value = _found(b"x" * 101, size=50)
        with self.assertRaises(ArtifactTooLargeError):
            self.sandbox.extract_file("/app/growing.txt", max_bytes=100)

    def test_existing_file_that_cannot_be_read_is_not_missing(self):
        self.mock_container.exec_run.return_value = _exec_run_result(1, b"head: permission denied")
        with self.assertRaises(ArtifactReadError) as ctx:
            self.sandbox.extract_file("/app/file.txt")
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

    def test_corrupt_readback_is_a_read_error(self):
        self.mock_container.exec_run.return_value = _exec_run_result(0, b"not-a-size\n")
        with self.assertRaises(ArtifactReadError):
            self.sandbox.extract_file("/app/file.txt")

    def test_docker_api_error_is_a_read_error_and_invalidates(self):
        self.mock_container.exec_run.side_effect = Exception("Connection refused")
        with self.assertRaises(ArtifactReadError) as ctx:
            self.sandbox.extract_file("/app/file.txt")
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)
        self.assertIsNotNone(self.sandbox.invalidated)

    def test_rejects_relative_path(self):
        with self.assertRaises(ValueError):
            self.sandbox.extract_file("relative.txt")
        self.mock_container.exec_run.assert_not_called()

    def test_path_is_a_positional_parameter_not_shell_text(self):
        malicious = "/app/file.txt; id > /tmp/pwned #"
        self.mock_container.exec_run.return_value = _exec_run_result(3, b"")
        with self.assertRaises(FileNotFoundError):
            self.sandbox.extract_file(malicious)
        cmd = self.mock_container.exec_run.call_args.kwargs["cmd"]
        self.assertEqual(cmd[:4], ["/bin/sh", "-c", READ, "autograder-read"])
        self.assertEqual(cmd[4], malicious)
        self.assertNotIn(malicious, READ)


if __name__ == "__main__":
    unittest.main()
