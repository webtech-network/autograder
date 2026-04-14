"""
Unit tests for SandboxContainer.extract_file.

Tests cover:
- Successful file extraction with UTF-8 content
- Missing file (FileNotFoundError)
- Oversized file (ValueError)
- Invalid tar stream (RuntimeError)
- Archive with no regular file (ValueError)
"""

import io
import tarfile
import unittest
from unittest.mock import MagicMock

from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ExtractedFile


def _make_tar_bytes(filename: str, content: bytes) -> bytes:
    """Build an in-memory tar archive containing a single file."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _make_tar_directory_only(dirname: str) -> bytes:
    """Build a tar archive containing only a directory entry (no regular file)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=dirname)
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    return buf.getvalue()


class TestExtractFile(unittest.TestCase):

    def setUp(self):
        self.mock_container = MagicMock()
        self.mock_container.id = "abc123def456"
        self.sandbox = SandboxContainer(
            language=Language.PYTHON,
            container_ref=self.mock_container,
        )

    def test_success_utf8(self):
        """Successful extraction of a UTF-8 text file."""
        content = "comparacoes: 10\nmovimentacoes: 4\n"
        tar_bytes = _make_tar_bytes("output.txt", content.encode("utf-8"))
        stat = {"name": "output.txt", "size": len(content)}

        self.mock_container.get_archive.return_value = (iter([tar_bytes]), stat)

        result = self.sandbox.extract_file("/app/output.txt")

        self.assertIsInstance(result, ExtractedFile)
        self.assertEqual(result.path, "/app/output.txt")
        self.assertEqual(result.content_text, content)
        self.assertEqual(result.size, len(content.encode("utf-8")))
        self.assertEqual(result.encoding, "utf-8")

    def test_success_latin1_fallback(self):
        """Falls back to latin-1 when content is not valid UTF-8."""
        content_bytes = b"\xe9\xe8\xea"  # latin-1 chars, invalid UTF-8
        tar_bytes = _make_tar_bytes("data.bin", content_bytes)
        stat = {"name": "data.bin", "size": len(content_bytes)}

        self.mock_container.get_archive.return_value = (iter([tar_bytes]), stat)

        result = self.sandbox.extract_file("/app/data.bin")

        self.assertEqual(result.encoding, "latin-1")
        self.assertEqual(result.content_bytes, content_bytes)

    def test_file_not_found(self):
        """Raises FileNotFoundError when Docker returns 404."""
        self.mock_container.get_archive.side_effect = Exception("404 Client Error: Not Found")

        with self.assertRaises(FileNotFoundError) as ctx:
            self.sandbox.extract_file("/app/missing.txt")

        self.assertIn("missing.txt", str(ctx.exception))

    def test_file_not_found_no_such(self):
        """Raises FileNotFoundError when Docker says 'No such file'."""
        self.mock_container.get_archive.side_effect = Exception("No such file or directory")

        with self.assertRaises(FileNotFoundError):
            self.sandbox.extract_file("/app/gone.txt")

    def test_oversized_file(self):
        """Raises ValueError when file exceeds max_bytes."""
        big_content = b"x" * 200
        tar_bytes = _make_tar_bytes("big.txt", big_content)
        stat = {"name": "big.txt", "size": 200}

        self.mock_container.get_archive.return_value = (iter([tar_bytes]), stat)

        with self.assertRaises(ValueError) as ctx:
            self.sandbox.extract_file("/app/big.txt", max_bytes=100)

        self.assertIn("exceeds maximum size", str(ctx.exception))

    def test_invalid_tar_stream(self):
        """Raises RuntimeError when tar stream is corrupted."""
        self.mock_container.get_archive.return_value = (iter([b"not-a-tar"]), {})

        with self.assertRaises(RuntimeError) as ctx:
            self.sandbox.extract_file("/app/file.txt")

        self.assertIn("Failed to read tar stream", str(ctx.exception))

    def test_no_regular_file_in_archive(self):
        """Raises ValueError when archive contains only a directory."""
        tar_bytes = _make_tar_directory_only("somedir")
        stat = {"name": "somedir", "size": 0}

        self.mock_container.get_archive.return_value = (iter([tar_bytes]), stat)

        with self.assertRaises(ValueError) as ctx:
            self.sandbox.extract_file("/app/somedir")

        self.assertIn("No regular file", str(ctx.exception))

    def test_docker_api_generic_error(self):
        """Raises RuntimeError for non-404 Docker errors."""
        self.mock_container.get_archive.side_effect = Exception("Connection refused")

        with self.assertRaises(RuntimeError) as ctx:
            self.sandbox.extract_file("/app/file.txt")

        self.assertIn("Failed to retrieve archive", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
