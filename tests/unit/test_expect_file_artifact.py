"""
Unit tests for ExpectFileArtifactTest.

Tests cover:
- Exact match success
- Contains match success
- Regex match success
- Content mismatch
- Missing artifact file
- Invalid regex pattern
- Invalid artifact path (absolute, traversal)
- Invalid match_mode
- Execution failure (timeout, runtime error)
- Normalization behavior
- Registration in InputOutputTemplate
"""

import unittest
from unittest.mock import MagicMock

from autograder.template_library.input_output import ExpectFileArtifactTest, InputOutputTemplate
from sandbox_manager.models.sandbox_models import (
    CommandResponse, ResponseCategory, ExtractedFile,
)


def _make_sandbox(stdout="", stderr="", exit_code=0, category=ResponseCategory.SUCCESS):
    """Return a mock sandbox whose run_commands returns the given CommandResponse."""
    sandbox = MagicMock()
    sandbox.run_commands.return_value = CommandResponse(
        stdout=stdout, stderr=stderr, exit_code=exit_code,
        execution_time=0.1, category=category,
    )
    sandbox.run_command.return_value = CommandResponse(
        stdout=stdout, stderr=stderr, exit_code=exit_code,
        execution_time=0.1, category=category,
    )
    return sandbox


def _make_extracted(content: str, path="/app/output.txt"):
    return ExtractedFile(
        path=path,
        content_bytes=content.encode("utf-8"),
        size=len(content.encode("utf-8")),
        content_text=content,
        encoding="utf-8",
    )


class TestExpectFileArtifactExactMatch(unittest.TestCase):
    """Tests for exact match logic in ExpectFileArtifactTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_exact_match_success(self):
        """Test success when artifact content exactly matches expected content."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("hello world")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="hello world",
        )

        self.assertEqual(result.score, 100.0)

    def test_exact_match_with_normalization(self):
        """Normalization strips trailing whitespace and normalizes line endings."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("line1  \r\nline2  \n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="line1\nline2",
        )

        self.assertEqual(result.score, 100.0)

    def test_exact_match_mismatch(self):
        """Test failure when artifact content does not match expected content."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("wrong content")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="expected content",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("wrong content", result.report)

    def test_exact_match_no_normalization(self):
        """When normalization is off, trailing whitespace matters."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("hello ")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="hello",
            normalization=False,
        )

        self.assertEqual(result.score, 0.0)


class TestExpectFileArtifactContainsMatch(unittest.TestCase):
    """Tests for contains match logic in ExpectFileArtifactTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_contains_match_success(self):
        """Test success when artifact content contains expected content."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("result: PASSED with 100%")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="report.txt",
            expected_content="PASSED",
            match_mode="contains",
        )

        self.assertEqual(result.score, 100.0)

    def test_contains_match_failure(self):
        """Test failure when artifact content does not contain expected content."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("result: FAILED")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="report.txt",
            expected_content="PASSED",
            match_mode="contains",
        )

        self.assertEqual(result.score, 0.0)


class TestExpectFileArtifactRegexMatch(unittest.TestCase):
    """Tests for regex match logic in ExpectFileArtifactTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_regex_match_success(self):
        """Test success when artifact content matches expected regex."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("comparacoes: 42\ntempo: 0.003s")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="metrics.txt",
            expected_content=r"comparacoes:\s*\d+",
            match_mode="regex",
        )

        self.assertEqual(result.score, 100.0)

    def test_regex_match_failure(self):
        """Test failure when artifact content does not match expected regex."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("no numbers here")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="metrics.txt",
            expected_content=r"comparacoes:\s*\d+",
            match_mode="regex",
        )

        self.assertEqual(result.score, 0.0)

    def test_invalid_regex(self):
        """Test handling of an invalid regex pattern."""
        sandbox = _make_sandbox()

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="[invalid(regex",
            match_mode="regex",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("regex", result.report.lower())


class TestExpectFileArtifactErrors(unittest.TestCase):
    """Tests for error handling in ExpectFileArtifactTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_missing_artifact(self):
        """Test behavior when the artifact file is not found in the container."""
        sandbox = _make_sandbox()
        sandbox.extract_file.side_effect = FileNotFoundError("File not found")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("output.txt", result.report)

    def test_extraction_error(self):
        """Test behavior when an error occurs during file extraction."""
        sandbox = _make_sandbox()
        sandbox.extract_file.side_effect = RuntimeError("tar stream corrupt")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("tar stream corrupt", result.report)

    def test_absolute_path_rejected(self):
        """Test that absolute artifact paths are rejected."""
        sandbox = _make_sandbox()

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="/etc/passwd",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("Invalid", result.report)

    def test_traversal_path_rejected(self):
        """Test that directory traversal in artifact paths is rejected."""
        sandbox = _make_sandbox()

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="../secret.txt",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("Invalid", result.report)

    def test_invalid_match_mode(self):
        """Test rejection of invalid match modes."""
        sandbox = _make_sandbox()

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="anything",
            match_mode="fuzzy",
        )

        self.assertEqual(result.score, 0.0)
        self.assertIn("fuzzy", result.report)

    def test_empty_artifact_path(self):
        """Test rejection of empty artifact paths."""
        sandbox = _make_sandbox()

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)


class TestExpectFileArtifactExecutionFailures(unittest.TestCase):
    """Tests for execution failure handling in ExpectFileArtifactTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_timeout(self):
        """Test handling of program execution timeout."""
        sandbox = _make_sandbox(
            stderr="Execution timed out after 30 seconds",
            exit_code=124,
            category=ResponseCategory.TIMEOUT,
        )

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)

    def test_runtime_error(self):
        """Test handling of program runtime errors."""
        sandbox = _make_sandbox(
            stderr="ZeroDivisionError: division by zero",
            exit_code=1,
            category=ResponseCategory.RUNTIME_ERROR,
        )

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="anything",
        )

        self.assertEqual(result.score, 0.0)


class TestExpectFileArtifactMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectFileArtifactTest."""

    def test_name(self):
        """Test the name property of the test."""
        self.assertEqual(ExpectFileArtifactTest().name, "expect_file_artifact")

    def test_description_not_empty(self):
        """Test that the description property is not empty."""
        self.assertTrue(len(ExpectFileArtifactTest().description) > 0)

    def test_parameter_descriptions(self):
        """Test the parameter_description property of the test."""
        params = ExpectFileArtifactTest().parameter_description
        names = [p.name for p in params]
        self.assertIn("artifact_path", names)
        self.assertIn("expected_content", names)
        self.assertIn("match_mode", names)
        self.assertIn("program_command", names)
        self.assertIn("inputs", names)
        self.assertIn("normalization", names)

    def test_registered_in_template(self):
        """Test that the test is correctly registered in InputOutputTemplate."""
        template = InputOutputTemplate()
        test = template.get_test("expect_file_artifact")
        self.assertIsInstance(test, ExpectFileArtifactTest)


if __name__ == "__main__":
    unittest.main()
