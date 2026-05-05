import logging
import re
from typing import List, Optional, Dict, Any, Type

from pydantic import BaseModel, Field

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ResponseCategory


# ===============================================================
# Base TestFunction for Executable Validations
# ===============================================================

class BaseExecutionTest(TestFunction):
    """
    Abstract base class for tests that involve running a student's code
    in a sandbox and handling basic execution results (timeouts, crashes).
    """

    def run_sandbox_execution(self, sandbox: SandboxContainer, inputs: list = None,
                              program_command: Optional[str] = None):
        """
        Executes the command inside the sandbox.
        `program_command` must already be a resolved string (or None).
        Returns the raw `output` from the sandbox run.
        """
        # Run with a pre-resolved command
        if program_command:
            safe_inputs = inputs if inputs is not None else []
            return sandbox.run_commands(safe_inputs, program_command=program_command)

        if inputs is None:
            raise ValueError("inputs parameter is required if no program_command is provided")
        command = ' '.join(inputs) if isinstance(inputs, list) else str(inputs)
        return sandbox.run_command(command)

    def check_for_base_errors(self, output, **kwargs) -> TestResult:
        """
        Checks for Timeout, Compilation Error, or Runtime Error in the sandbox output.
        Returns a TestResult with score 0.0 if an error is found, or None if successful.
        """
        if output.category == ResponseCategory.TIMEOUT:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.timeout", locale=kwargs.get("locale"), time=output.execution_time)
            )

        if output.category == ResponseCategory.COMPILATION_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.compilation_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        if output.category == ResponseCategory.RUNTIME_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.runtime_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        if output.category == ResponseCategory.SYSTEM_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.system_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        return None

# ===============================================================
# TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(BaseExecutionTest):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.

    Supports multi-language submissions through dynamic command resolution.
    """

    @property
    def name(self):
        return "expect_output"

    @property
    def description(self):
        return t("io.expect_output.description")

    @property
    def required_file(self):
        """Returns the name of the file required for this test, or None if not applicable."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("inputs", t("io.expect_output.params.inputs"), "list of strings"),
            ParamDescription("expected_output", t("io.expect_output.params.expected"), "string"),
            ParamDescription("program_command", t("io.expect_output.params.program_command"), "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        """
        Execute the test by comparing program output with expected output.
        """
        inputs = kwargs.get("inputs")
        expected_output = kwargs.get("expected_output", "")
        program_command = kwargs.get("program_command")
        locale = kwargs.get("locale")

        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                inputs=inputs,
                program_command=program_command,
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output, **kwargs)
            if error_result:
                return error_result

            # Standard I/O Comparison if execution succeeded
            actual_output = output.stdout.strip()
            expected = expected_output.strip()

            if actual_output == expected:
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report=t("io.expect_output.report.success", locale=locale)
                )
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.failure", locale=locale, expected=expected, actual=actual_output)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.internal_error", locale=locale, error=str(e))
            )

class DontFailTest(BaseExecutionTest):
    """
    Tests that a command-line program does NOT crash when given a specific input.

    Unlike ExpectOutputTest, this test ignores the program's stdout entirely.
    It only checks that execution completes without a runtime error, compilation
    error, or timeout. Useful for validating error handling (e.g., sending a
    string when the program expects a number).
    """

    @property
    def name(self):
        return "dont_fail"

    @property
    def description(self):
        return t("io.dont_fail.description")

    @property
    def required_file(self):
        """Returns the name of the file required for this test, or None if not applicable."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("input", t("io.expect_output.params.inputs"), "string"),
            ParamDescription("program_command", t("io.expect_output.params.program_command"), "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        """
        Execute the test by verifying the program doesn't crash with given input.
        """
        user_input = kwargs.get("user_input", "")
        program_command = kwargs.get("program_command")
        locale = kwargs.get("locale")

        try:
            # Reformat scalar input to standard list
            inputs = [user_input] if user_input is not None and user_input != "" else []
            
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                inputs=inputs,
                program_command=program_command,
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output, **kwargs)
            if error_result:
                return error_result

            # Program completed without crashing — success!
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("io.dont_fail.report.success", locale=locale)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.internal_error", locale=locale, error=str(e))
            )



# ===============================================================
# TestFunction for File Artifact Validation
# ===============================================================

class ExpectFileArtifactTest(BaseExecutionTest):
    """
    Tests a command-line program by running it, then extracting a generated
    file from the sandbox and comparing its content against expected values.

    Supports exact, contains, and regex matching modes.
    """

    @property
    def name(self):
        return "expect_file_artifact"

    @property
    def description(self):
        return t("io.expect_file_artifact.description")

    @property
    def required_file(self):
        """Returns the name of the file required for this test, or None if not applicable."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("io.expect_file_artifact.params.program_command"), "string or dict"),
            ParamDescription("artifact_path", t("io.expect_file_artifact.params.artifact_path"), "string"),
            ParamDescription("expected_content", t("io.expect_file_artifact.params.expected_content"), "string"),
            ParamDescription("match_mode", t("io.expect_file_artifact.params.match_mode"), "string"),
            ParamDescription("inputs", t("io.expect_file_artifact.params.inputs"), "list of strings"),
            ParamDescription("normalization", t("io.expect_file_artifact.params.normalization"), "boolean"),
        ]

    @staticmethod
    def _validate_artifact_path(artifact_path: str) -> Optional[str]:
        """Return an error message if the path is unsafe, else None."""
        if not artifact_path:
            return "artifact_path is required"
        if artifact_path.startswith("/") or ".." in artifact_path.split("/"):
            return f"Invalid artifact_path (absolute or traversal): {artifact_path}"
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize line endings and strip trailing whitespace per line."""
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "\n".join(line.rstrip() for line in lines).strip()

    @staticmethod
    def _match(actual: str, expected: str, mode: str) -> bool:
        if mode == "contains":
            return expected in actual
        if mode == "regex":
            return bool(re.search(expected, actual))
        return actual == expected

    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        """
        Execute the test by extracting a file from the sandbox and comparing its content.
        """
        program_command = kwargs.get("program_command")
        artifact_path = kwargs.get("artifact_path", "")
        expected_content = kwargs.get("expected_content", "")
        match_mode = kwargs.get("match_mode", "exact")
        inputs = kwargs.get("inputs")
        normalization = kwargs.get("normalization", True)
        locale = kwargs.get("locale")

        # 1. Validation
        validation_error = self._validate_params(artifact_path, match_mode, expected_content, locale)
        if validation_error:
            return validation_error

        # 2. Execution
        try:
            output = self.run_sandbox_execution(sandbox=sandbox, inputs=inputs, program_command=program_command)
            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result
        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_output.report.internal_error", locale=locale, error=str(e)))

        # 3. Extraction and Comparison
        return self._extract_and_compare(sandbox, artifact_path, expected_content, match_mode, normalization, locale)

    def _validate_params(self, artifact_path: str, match_mode: str, expected_content: str, locale: str) -> Optional[TestResult]:
        """Validate input parameters for the test."""
        path_error = self._validate_artifact_path(artifact_path)
        if path_error:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.invalid_path", locale=locale, error=path_error))

        if match_mode not in ("exact", "contains", "regex"):
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.invalid_match_mode", locale=locale, mode=match_mode))

        if match_mode == "regex":
            try:
                re.compile(expected_content)
            except re.error as e:
                return TestResult(test_name=self.name, score=0.0,
                                  report=t("io.expect_file_artifact.report.invalid_regex", locale=locale, error=str(e)))
        return None

    def _extract_and_compare(self, sandbox: SandboxContainer, path: str, expected: str, 
                             mode: str, normalization: bool, locale: str) -> TestResult:
        """Extract the artifact and compare its content."""
        try:
            extracted = sandbox.extract_file(f"/app/{path}")
        except FileNotFoundError:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.file_not_found", locale=locale, path=path))
        except (ValueError, RuntimeError) as e:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.extraction_error", locale=locale, error=str(e)))

        actual = extracted.content_text
        if normalization:
            actual = self._normalize(actual)
            expected = self._normalize(expected)

        if self._match(actual, expected, mode):
            return TestResult(test_name=self.name, score=100.0,
                              report=t("io.expect_file_artifact.report.success", locale=locale, path=path))

        return TestResult(test_name=self.name, score=0.0,
                          report=t("io.expect_file_artifact.report.mismatch", locale=locale,
                                   path=path, expected=expected, actual=actual))


class InputOutputTemplate(Template):
    """
    A template for command-line I/O assignments. It uses the SandboxExecutor
    to securely run student programs and validate their console output.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "expect_output": ExpectOutputTest(),
            "dont_fail": DontFailTest(),
            "expect_file_artifact": ExpectFileArtifactTest(),
        }

    @property
    def template_name(self):
        return t("io.template.name")

    @property
    def template_description(self):
        return t("io.template.description")

    @property
    def requires_sandbox(self) -> bool:
        return True

    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
