"""
Unit tests for ExpectFileArtifactTest.

Tests cover:
- Exact match success
- Contains match success
- Regex match success
- Content mismatch
- Missing artifact file
- Invalid regex pattern, artifact path (absolute, traversal) and match_mode
  are rejected by the parameter contract before any execution
- Execution failure (timeout, runtime error)
- Normalization behavior
- Registration in InputOutputTemplate
"""

from pydantic import ValidationError

from tests.evaluator_calls import invoke
import unittest
from autograder.models.evaluation_error import EvaluationError
from unittest.mock import MagicMock

from autograder.template_library.input_output import ExpectFileArtifactTest, InputOutputTemplate
from autograder.models.process import ProcessResult, ProcessStatus
from sandbox_manager.models.sandbox_models import ExtractedFile


def _make_sandbox(stdout="", stderr="", exit_code=0, timed_out=False):
    """Return a mock session whose run_process returns the given process result."""
    sandbox = MagicMock()
    sandbox.run_process.return_value = (
        ProcessResult(ProcessStatus.TIMED_OUT, None, stdout, stderr, duration=30) if timed_out
        else ProcessResult(ProcessStatus.EXITED, exit_code, stdout, stderr, duration=0.1))
    return sandbox


def _make_extracted(content: str, path="output.txt"):
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
        sandbox.read_artifact.return_value = _make_extracted("hello world")

        result = invoke(self.test,
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="hello world",
        )

        self.assertEqual(result.score, 100.0)

    def test_exact_match_with_normalization(self):
        """Normalization strips trailing whitespace and normalizes line endings."""
        sandbox = _make_sandbox()
        sandbox.read_artifact.return_value = _make_extracted("line1  \r\nline2  \n")

        result = invoke(self.test,
            files=None, sandbox=sandbox,
            program_command="python3 main.py",
            artifact_path="output.txt",
            expected_content="line1\nline2",
        )

        self.assertEqual(result.score, 100.0)

    def test_exact_match_mismatch(self):
        """Test failure when artifact content does not match expected content."""
        sandbox = _make_sandbox()
        sandbox.read_artifact.return_value = _make_extracted("wrong content")

        result = invoke(self.test,
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
        sandbox.read_artifact.return_value = _make_extracted("hello ")

        result = invoke(self.test,
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
        sandbox.read_artifact.return_value = _make_extracted("result: PASSED with 100%")

        result = invoke(self.test,
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
        sandbox.read_artifact.return_value = _make_extracted("result: FAILED")

        result = invoke(self.test,
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
        sandbox.read_artifact.return_value = _make_extracted("comparacoes: 42\ntempo: 0.003s")

        result = invoke(self.test,
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
        sandbox.read_artifact.return_value = _make_extracted("no numbers here")

        result = invoke(self.test,
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

        with self.assertRaises(ValidationError):
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="output.txt",
                expected_content="[invalid(regex",
                match_mode="regex",
            )
        sandbox.run_process.assert_not_called()

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_missing_artifact(self):
        """Test behavior when the artifact file is not found in the container."""
        sandbox = _make_sandbox()
        sandbox.read_artifact.side_effect = FileNotFoundError("File not found")

        result = invoke(self.test,
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
        sandbox.read_artifact.side_effect = RuntimeError("tar stream corrupt")

        with self.assertRaises(EvaluationError) as error:
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="output.txt",
                expected_content="anything",
            )
        self.assertEqual(error.exception.category, "capability")
        self.assertNotIn("tar stream corrupt", error.exception.message)

    def test_absolute_path_rejected(self):
        """Test that absolute artifact paths are rejected."""
        sandbox = _make_sandbox()

        with self.assertRaises(ValidationError):
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="/etc/passwd",
                expected_content="anything",
            )
        sandbox.run_process.assert_not_called()

    def test_traversal_path_rejected(self):
        """Test that directory traversal in artifact paths is rejected."""
        sandbox = _make_sandbox()

        with self.assertRaises(ValidationError):
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="../secret.txt",
                expected_content="anything",
            )
        sandbox.run_process.assert_not_called()

    def test_invalid_match_mode(self):
        """Test rejection of invalid match modes."""
        sandbox = _make_sandbox()

        with self.assertRaises(ValidationError):
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="output.txt",
                expected_content="anything",
                match_mode="fuzzy",
            )
        sandbox.run_process.assert_not_called()

    def test_empty_artifact_path(self):
        """Test rejection of empty artifact paths."""
        sandbox = _make_sandbox()

        with self.assertRaises(ValidationError):
            invoke(self.test,
                files=None, sandbox=sandbox,
                program_command="python3 main.py",
                artifact_path="",
                expected_content="anything",
            )
        sandbox.run_process.assert_not_called()

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectFileArtifactTest()

    def test_timeout(self):
        """Test handling of program execution timeout."""
        sandbox = _make_sandbox(
            stderr="Execution timed out after 30 seconds",
            exit_code=124,
            timed_out=True,
        )

        result = invoke(self.test,
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
        )

        result = invoke(self.test,
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
        """Parameter documentation comes from the contract's field descriptions."""
        properties = ExpectFileArtifactTest().config_schema.model_json_schema()["properties"]
        self.assertTrue(all(field["description"] for field in properties.values()))
        names = list(properties)
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
