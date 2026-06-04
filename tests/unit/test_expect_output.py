"""
Unit tests for ExpectOutputTest.

Tests cover:
- Exact match success
- Exact match with normalization (trailing spaces)
- Exact match without normalization
- Mixed line endings (CRLF, LF, CR)
- Timeout, compilation error, runtime error handling
- Registration in InputOutputTemplate
"""

import unittest
from unittest.mock import MagicMock

from autograder.template_library.input_output import ExpectOutputTest, InputOutputTemplate
from sandbox_manager.models.sandbox_models import CommandResponse, ResponseCategory


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


class TestExpectOutputNormalization(unittest.TestCase):
    """Tests for whitespace normalization in ExpectOutputTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectOutputTest()

    def test_exact_match_success(self):
        """Test success when output exactly matches expected output."""
        sandbox = _make_sandbox(stdout="hello world\n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="hello world",
            program_command="echo hello world",
        )

        self.assertEqual(result.score, 100.0)

    def test_normalization_strips_trailing_spaces(self):
        """Test that normalization removes trailing spaces on each line."""
        sandbox = _make_sandbox(stdout="line1  \nline2  \n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="line1\nline2",
            program_command="python3 main.py",
            normalization=True,
        )

        self.assertEqual(result.score, 100.0)

    def test_normalization_handles_crlf(self):
        """Test that normalization converts CRLF to LF."""
        sandbox = _make_sandbox(stdout="line1\r\nline2\r\n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="line1\nline2",
            program_command="python3 main.py",
            normalization=True,
        )

        self.assertEqual(result.score, 100.0)

    def test_normalization_handles_cr(self):
        """Test that normalization converts CR to LF."""
        sandbox = _make_sandbox(stdout="line1\rline2\r")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="line1\nline2",
            program_command="python3 main.py",
            normalization=True,
        )

        self.assertEqual(result.score, 100.0)

    def test_normalization_preserves_blank_lines(self):
        """Test that normalization preserves intentional blank lines."""
        sandbox = _make_sandbox(stdout="line1\n\nline2\n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="line1\n\nline2",
            program_command="python3 main.py",
            normalization=True,
        )

        self.assertEqual(result.score, 100.0)

    def test_no_normalization_fails_on_trailing_space(self):
        """Test that without normalization, trailing spaces matter."""
        sandbox = _make_sandbox(stdout="hello ")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="hello",
            program_command="echo hello",
            normalization=False,
        )

        self.assertEqual(result.score, 0.0)

    def test_normalization_default_true(self):
        """Test that normalization defaults to True."""
        sandbox = _make_sandbox(stdout="hello  \n")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output="hello",
            program_command="echo hello",
            # normalization parameter omitted, should default to True
        )

        self.assertEqual(result.score, 100.0)

    def test_real_world_example_trailing_space_in_output(self):
        """
        Real-world example from issue:
        Student output has trailing space, expected doesn't.
        """
        student_output = "Personagem mais popular:\nCodigo: 101\nNome: Mickey\nFilme: Fantasia\nAno: 1928\nNota: 9.80 "
        expected = "Personagem mais popular:\nCodigo: 101\nNome: Mickey\nFilme: Fantasia\nAno: 1928\nNota: 9.80"

        sandbox = _make_sandbox(stdout=student_output)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=[], expected_output=expected,
            program_command="python3 main.py",
            normalization=True,
        )

        self.assertEqual(result.score, 100.0)


class TestExpectOutputErrors(unittest.TestCase):
    """Tests for error handling in ExpectOutputTest."""

    def setUp(self):
        """Set up the test case."""
        self.test = ExpectOutputTest()

    def test_timeout(self):
        """Test handling of program execution timeout."""
        sandbox = _make_sandbox(
            stderr="Execution timed out",
            category=ResponseCategory.TIMEOUT,
        )

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=["test"], expected_output="expected",
            program_command="python3 main.py",
        )

        self.assertEqual(result.score, 0.0)

    def test_compilation_error(self):
        """Test handling of compilation errors."""
        sandbox = _make_sandbox(
            stderr="SyntaxError: invalid syntax",
            category=ResponseCategory.COMPILATION_ERROR,
        )

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=["test"], expected_output="expected",
            program_command="java Main",
        )

        self.assertEqual(result.score, 0.0)

    def test_runtime_error(self):
        """Test handling of runtime errors."""
        sandbox = _make_sandbox(
            stderr="ZeroDivisionError: division by zero",
            category=ResponseCategory.RUNTIME_ERROR,
        )

        result = self.test.execute(
            files=None, sandbox=sandbox,
            inputs=["test"], expected_output="expected",
            program_command="python3 main.py",
        )

        self.assertEqual(result.score, 0.0)


class TestExpectOutputMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectOutputTest."""

    def test_name(self):
        """Test the name property."""
        self.assertEqual(ExpectOutputTest().name, "expect_output")

    def test_normalization_in_parameter_descriptions(self):
        """Test that normalization parameter is documented."""
        params = ExpectOutputTest().parameter_description
        names = [p.name for p in params]
        self.assertIn("normalization", names)

    def test_registered_in_template(self):
        """Test that the test is registered in InputOutputTemplate."""
        template = InputOutputTemplate()
        test = template.get_test("expect_output")
        self.assertIsInstance(test, ExpectOutputTest)


if __name__ == "__main__":
    unittest.main()
