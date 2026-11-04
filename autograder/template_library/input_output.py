import logging
import re
from pathlib import PurePosixPath
from typing import Annotated, Any, Dict, Iterable, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import EvaluationInput, ParameterIssue, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.models.language import Language, LanguageId
from autograder.translations import t
from autograder.models.execution import ExecutionSession
from sandbox_manager.models.sandbox_models import ResponseCategory
from autograder.models.evaluation_error import EvaluationError


# ===============================================================
# Evaluator-owned parameter contracts
# ===============================================================

PROGRAM_COMMAND = ("Command that runs the program: a nonempty string, a map with a command for every "
                   "allowed language, or 'CMD' for the conventional per-language default.")

Nonempty = Annotated[str, Field(min_length=1)]
Command = Nonempty | dict[LanguageId, Nonempty]

#: The ``CMD`` placeholder: the conventional entry point of each runtime. This is
#: the only default-command table. A language without an entry cannot use ``CMD``
#: (``MISSING_LANGUAGE_COMMAND`` at compilation); authors can always write an
#: explicit command or a language map instead.
DEFAULT_COMMANDS: Dict[Language, str] = {
    Language.PYTHON: "python3 main.py",
    Language.JAVA: "java Main",
    Language.NODE: "node index.js",
    Language.CPP: "./a.out",
    Language.C: "./a.out",
}
DEFAULT_COMMAND = "CMD"


STRICT = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpectOutputParameters(BaseModel):
    model_config = STRICT
    inputs: List[str] = Field(default_factory=list, description=t("io.expect_output.params.inputs"))
    expected_output: str = Field(description=t("io.expect_output.params.expected"))
    program_command: Command = Field(description=PROGRAM_COMMAND)
    normalization: bool = Field(default=True, description=t("io.expect_output.params.normalization_desc"))


class DontFailParameters(BaseModel):
    model_config = STRICT
    user_input: str = Field(default="", description="Single line sent to the program's standard input; empty sends nothing.")
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
# Base TestFunction for Executable Validations
# ===============================================================

class BaseExecutionTest(TestFunction):
    """
    Abstract base class for tests that involve running a student's code
    in a sandbox and handling basic execution results (timeouts, crashes).
    """

    uses_context_files = True
    required_capabilities = ("sandbox_execution",)

    def validate_parameters(self, parameters: Dict[str, Any], *,
                            languages: Tuple[str, ...]) -> Iterable[ParameterIssue]:
        """A language map or ``CMD`` must name a command for every allowed language."""
        command = parameters["program_command"]
        if isinstance(command, dict):
            covered = set(command)
        elif command == DEFAULT_COMMAND:
            covered = {language.value for language in DEFAULT_COMMANDS}
        else:
            return
        if not set(languages).issubset(covered):
            yield ParameterIssue("MISSING_LANGUAGE_COMMAND", ("program_command",),
                                 "Command map must cover every allowed language")

    @staticmethod
    def resolve_command(program_command: Any, evaluation: EvaluationInput) -> str:
        """The command for the bound submission language.

        A plain string is used verbatim; a language map and ``CMD`` select by
        ``evaluation.language``. Compilation guarantees coverage, so a missing
        entry here means the evaluator was invoked outside a compiled plan.
        """
        if isinstance(program_command, str) and program_command != DEFAULT_COMMAND:
            return program_command
        if evaluation.language is None:
            raise EvaluationError("LANGUAGE_REQUIRED", "A language is required to select the program command.", "submission")
        table = program_command if isinstance(program_command, dict) else {
            language.value: command for language, command in DEFAULT_COMMANDS.items()}
        try:
            return table[evaluation.language.value]
        except KeyError:
            raise EvaluationError("MISSING_LANGUAGE_COMMAND", "No program command is defined for this language.",
                                  "submission") from None

    @staticmethod
    def require_session(evaluation: EvaluationInput) -> ExecutionSession:
        """The execution session bound to this evaluator by its capability declaration."""
        if evaluation.session is None:
            raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.", "capability")
        return evaluation.session

    def run_sandbox_execution(self, sandbox: ExecutionSession, inputs: list = None,
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

    def check_for_base_errors(self, output, locale: Optional[str] = None) -> Optional[TestResult]:
        """
        Checks for Timeout, Compilation Error, or Runtime Error in the sandbox output.
        Returns a TestResult with score 0.0 if an error is found, or None if successful.
        """
        if output.category == ResponseCategory.TIMEOUT:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.timeout", locale=locale, time=output.execution_time)
            )

        if output.category == ResponseCategory.COMPILATION_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.compilation_error", locale=locale, error=output.stderr)
            )

        if output.category == ResponseCategory.RUNTIME_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.runtime_error", locale=locale, error=output.stderr)
            )

        if output.category == ResponseCategory.SYSTEM_ERROR:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not complete evaluation.", "capability", True)

        return None

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize text for output comparison by:
        1. Converting all line endings to \n
        2. Removing trailing whitespace from each line
        3. Removing leading and trailing whitespace from the entire output
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "\n".join(line.rstrip() for line in lines).strip()

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
        try:
            output = self.run_sandbox_execution(
                sandbox=self.require_session(evaluation),
                inputs=inputs,
                program_command=self.resolve_command(program_command, evaluation),
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output, locale)
            if error_result:
                return error_result

            # Standard I/O Comparison if execution succeeded
            actual_output = output.stdout
            expected = expected_output

            if normalization:
                actual_output = self._normalize(actual_output)
                expected = self._normalize(expected)

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
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not complete evaluation.", "capability", True) from e

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

    def execute(self, evaluation: EvaluationInput, *, program_command: Any, user_input: str = "") -> TestResult:
        """
        Execute the test by verifying the program doesn't crash with given input.
        """
        locale = evaluation.locale
        try:
            # Reformat scalar input to standard list
            inputs = [user_input] if user_input else []

            output = self.run_sandbox_execution(
                sandbox=self.require_session(evaluation),
                inputs=inputs,
                program_command=self.resolve_command(program_command, evaluation),
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output, locale)
            if error_result:
                return error_result

            # Program completed without crashing — success!
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("io.dont_fail.report.success", locale=locale)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not complete evaluation.", "capability", True) from e



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
        sandbox = self.require_session(evaluation)
        try:
            output = self.run_sandbox_execution(sandbox=sandbox, inputs=inputs,
                                                program_command=self.resolve_command(program_command, evaluation))
            error_result = self.check_for_base_errors(output, locale)
            if error_result:
                return error_result
        except (ValueError, TimeoutError, RuntimeError) as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not complete evaluation.", "capability", True) from e

        return self._extract_and_compare(sandbox, artifact_path, expected_content, match_mode, normalization, locale)

    def _extract_and_compare(self, sandbox: ExecutionSession, path: str, expected: str,
                             mode: str, normalization: bool, locale: str) -> TestResult:
        """Extract the artifact and compare its content."""
        try:
            extracted = sandbox.read_artifact(path)
        except FileNotFoundError:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.expect_file_artifact.report.file_not_found", locale=locale, path=path))
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
