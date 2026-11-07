import re
from pathlib import PurePosixPath
from typing import Annotated, Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autograder.models.abstract.execution_test import BaseExecutionTest
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import EvaluationInput
from autograder.models.dataclass.test_result import TestResult
from autograder.models.language import LanguageId
from autograder.translations import t
from autograder.models.execution import ExecutionSession
from autograder.models.process import SandboxExhausted
from autograder.models.evaluation_error import EvaluationError


# ===============================================================
# Evaluator-owned parameter contracts
# ===============================================================

PROGRAM_COMMAND = ("Command that runs the program: a nonempty string, a map with a command for every "
                   "allowed language, or 'CMD' for the conventional per-language default. It runs without a "
                   "shell for every test: compile in preparation.setup_commands, never here; standalone shell "
                   "operators (&&, |, ;, >, ...) are rejected.")

Nonempty = Annotated[str, Field(min_length=1)]
Command = Nonempty | dict[LanguageId, Nonempty]



STRICT = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpectOutputParameters(BaseModel):
    model_config = STRICT
    inputs: List[str] = Field(default_factory=list, description=t("io.expect_output.params.inputs"))
    expected_output: str = Field(description=t("io.expect_output.params.expected"))
    program_command: Command = Field(description=PROGRAM_COMMAND)
    normalization: bool = Field(default=True, description=t("io.expect_output.params.normalization_desc"))


class DontFailParameters(BaseModel):
    model_config = STRICT
    inputs: List[str] = Field(default_factory=list, description=t("io.dont_fail.params.inputs"))
    program_command: Command = Field(description=PROGRAM_COMMAND)


class ArtifactParameters(BaseModel):
    model_config = STRICT
    inputs: List[str] = Field(default_factory=list, description=t("io.expect_file_artifact.params.inputs"))
    program_command: Command = Field(description=PROGRAM_COMMAND)
    artifact_path: str = Field(min_length=1, description=t("io.expect_file_artifact.params.artifact_path"))
    expected_content: str = Field(description=t("io.expect_file_artifact.params.expected_content"))
    match_mode: Literal["exact", "contains", "regex"] = Field(
        default="exact", description=t("io.expect_file_artifact.params.match_mode"))
    normalization: bool = Field(default=True, description=t("io.expect_file_artifact.params.normalization"))

    @model_validator(mode="after")
    def validate_artifact(self):
        if (self.artifact_path.startswith('/') or self.artifact_path == '.'
                or str(PurePosixPath(self.artifact_path)) != self.artifact_path
                or '..' in PurePosixPath(self.artifact_path).parts
                or '\\' in self.artifact_path or '\x00' in self.artifact_path):
            raise ValueError("artifact_path must be a normalized relative path without traversal or control characters")
        if self.match_mode == "regex":
            try:
                re.compile(self.expected_content)
            except re.error as exc:
                raise ValueError("expected_content must be a valid regular expression") from exc
        return self


# ===============================================================
# TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(BaseExecutionTest):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.

    Supports multi-language submissions through dynamic command resolution.
    """

    config_schema = ExpectOutputParameters

    @property
    def name(self):
        return "expect_output"

    @property
    def description(self):
        return t("io.expect_output.description")

    def execute(self, evaluation: EvaluationInput, *, program_command: Any, expected_output: str,
                inputs: Optional[List[str]] = None, normalization: bool = True) -> TestResult:
        """
        Execute the test by comparing program output with expected output.
        """
        locale = evaluation.locale
        result = self.run_program(evaluation, program_command, inputs)
        failure = self.assessed_failure(result, locale)
        if failure:
            return failure

        actual_output = result.stdout
        expected = expected_output
        if normalization:
            actual_output = self._normalize(actual_output)
            expected = self._normalize(expected)

        if actual_output == expected:
            return TestResult(test_name=self.name, score=100.0,
                              report=t("io.expect_output.report.success", locale=locale))
        return TestResult(test_name=self.name, score=0.0,
                          report=t("io.expect_output.report.failure", locale=locale, expected=expected,
                                   actual=actual_output))

class DontFailTest(BaseExecutionTest):
    """
    Tests that a command-line program does NOT crash when given a specific input.

    Unlike ExpectOutputTest, this test ignores the program's stdout entirely.
    It only checks that execution completes without a runtime error, compilation
    error, or timeout. Useful for validating error handling (e.g., sending a
    string when the program expects a number).
    """

    config_schema = DontFailParameters

    @property
    def name(self):
        return "dont_fail"

    @property
    def description(self):
        return t("io.dont_fail.description")

    def execute(self, evaluation: EvaluationInput, *, program_command: Any,
                inputs: Optional[List[str]] = None) -> TestResult:
        """
        Execute the test by verifying the program doesn't crash with given input.
        """
        locale = evaluation.locale
        result = self.run_program(evaluation, program_command, inputs)
        failure = self.assessed_failure(result, locale)
        if failure:
            return failure
        return TestResult(test_name=self.name, score=100.0, report=t("io.dont_fail.report.success", locale=locale))


# ===============================================================
# TestFunction for File Artifact Validation
# ===============================================================

class ExpectFileArtifactTest(BaseExecutionTest):
    """
    Tests a command-line program by running it, then extracting a generated
    file from the sandbox and comparing its content against expected values.

    Supports exact, contains, and regex matching modes. Path safety, match
    modes and regular expressions are enforced by its parameter contract
    before any execution.
    """

    config_schema = ArtifactParameters

    @property
    def name(self):
        return "expect_file_artifact"

    @property
    def description(self):
        return t("io.expect_file_artifact.description")

    @staticmethod
    def _match(actual: str, expected: str, mode: str) -> bool:
        if mode == "contains":
            return expected in actual
        if mode == "regex":
            return bool(re.search(expected, actual))
        return actual == expected

    def execute(self, evaluation: EvaluationInput, *, program_command: Any, artifact_path: str,
                expected_content: str, match_mode: str = "exact", inputs: Optional[List[str]] = None,
                normalization: bool = True) -> TestResult:
        """
        Execute the test by extracting a file from the sandbox and comparing its content.
        """
        locale = evaluation.locale
        result = self.run_program(evaluation, program_command, inputs)
        failure = self.assessed_failure(result, locale)
        if failure:
            return failure
        return self._extract_and_compare(self.require_session(evaluation), artifact_path, expected_content,
                                         match_mode, normalization, locale)

    def _extract_and_compare(self, sandbox: ExecutionSession, path: str, expected: str,
                             mode: str, normalization: bool, locale: str) -> TestResult:
        """Extract the artifact and compare its content."""
        try:
            extracted = sandbox.read_artifact(path)
        except FileNotFoundError:
            # Only a missing file is the student's; an unknown/invalidated session
            # or failed readback is an infrastructure error below.
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.file_not_found", locale=locale, path=path))
        except SandboxExhausted:
            return TestResult(test_name=self.name, score=0.0, report=t("io.execution.exhausted", locale=locale))
        except (ValueError, RuntimeError) as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not retrieve the assessed artifact.", "capability", True) from e

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
    """Command-line I/O: evaluators that run the student program."""

    def __init__(self):
        super().__init__(t("io.template.name"), t("io.template.description"),
                         [ExpectOutputTest(), DontFailTest(), ExpectFileArtifactTest()])
