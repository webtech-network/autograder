import logging
import re
from typing import List, Optional

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
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

    def check_for_base_errors(self, output) -> TestResult:
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
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("inputs", t("io.expect_output.params.inputs"), "list of strings"),
            ParamDescription("expected_output", t("io.expect_output.params.expected"), "string"),
            ParamDescription("program_command", t("io.expect_output.params.program_command"), "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, *args, inputs: list = None, expected_output: str = "",
                program_command: Optional[str] = None, **kwargs) -> TestResult:
        """
        Execute the test by comparing program output with expected output.
        """
        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                inputs=inputs,
                program_command=program_command,
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output)
            if error_result:
                return error_result

            # Standard I/O Comparison if execution succeeded
            actual_output = output.stdout.strip()
            expected = expected_output.strip()

            if actual_output == expected:
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report=t("io.expect_output.report.success", locale=kwargs.get("locale"))
                )
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.failure", locale=kwargs.get("locale"), expected=expected, actual=actual_output)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.internal_error", locale=kwargs.get("locale"), error=str(e))
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
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("input", t("io.expect_output.params.inputs"), "string"),
            ParamDescription("program_command", t("io.expect_output.params.program_command"), "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, *args, user_input: str = "",
                program_command: Optional[str] = None, **kwargs) -> TestResult:
        """
        Execute the test by verifying the program doesn't crash with given input.
        """
        try:
            # Reformat scalar input to standard list
            inputs = [user_input] if user_input is not None and user_input != "" else []
            
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                inputs=inputs,
                program_command=program_command,
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output)
            if error_result:
                return error_result

            # Program completed without crashing — success!
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("io.dont_fail.report.success", locale=kwargs.get("locale"))
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.expect_output.report.internal_error", locale=kwargs.get("locale"), error=str(e))
            )



# ===============================================================
# TestFunction for Forbidden Import Detection
# ===============================================================

class ForbiddenImportTest(TestFunction):
    """
    Tests that a submission does NOT import any of the specified forbidden libraries.

    Performs static analysis on submission file contents using language-aware
    regex patterns. Supports Python, Java, JavaScript/Node, C and C++.
    """

    # Language-specific regex builders: each returns a compiled pattern
    # that matches an import of the given library name.
    IMPORT_PATTERNS = {
        Language.PYTHON: [
            # import lib  /  import lib as x  /  import lib.sub
            r'^\s*import\s+{lib}\b',
            # from lib import ...  /  from lib.sub import ...
            r'^\s*from\s+{lib}\b',
        ],
        Language.JAVA: [
            # import pkg.Class;  /  import static pkg.Class.method;
            r'^\s*import\s+(?:static\s+)?{lib}\b',
        ],
        Language.NODE: [
            # require('lib')  /  require("lib")
            r"\brequire\s*\(\s*['\"]{{lib}}['\"]\s*\)",
            # import ... from 'lib'  /  import 'lib'
            r'^\s*import\s+.*?[\'"]{{lib}}[\'"]',
        ],
        Language.CPP: [
            # #include <lib>  /  #include <lib/header.h>  /  #include "lib..."
            r'^\s*#\s*include\s*[<"]{lib}[/\.>"]',
        ],
        Language.C: [
            r'^\s*#\s*include\s*[<"]{lib}[/\.>"]',
        ],
    }

    @property
    def name(self):
        return "forbidden_import"

    @property
    def description(self):
        return t("io.forbidden_import.description")

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription(
                "forbidden_imports",
                t("io.forbidden_import.params.libraries"),
                "list of strings"
            ),
            ParamDescription(
                "submission_language",
                t("io.forbidden_import.params.language"),
                "string or Language enum"
            ),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_patterns(self, library: str, language: Language) -> List[re.Pattern]:
        """Return compiled regex patterns for detecting *library* in *language*."""
        templates = self.IMPORT_PATTERNS.get(language, [])
        compiled: List[re.Pattern] = []
        for tmpl in templates:
            # Support both {lib} and {{lib}} placeholders (Node patterns use
            # double-braces to survive the first .format call on the class body).
            raw = tmpl.replace('{{lib}}', library).replace('{lib}', re.escape(library))
            compiled.append(re.compile(raw, re.MULTILINE))
        return compiled

    def _scan_file(self, content: str, forbidden: List[str],
                   language: Language) -> List[str]:
        """
        Scan *content* for any forbidden imports.

        Returns a list of human-readable violation strings.
        """
        violations: List[str] = []
        for lib in forbidden:
            patterns = self._build_patterns(lib, language)
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    violations.append(lib)
                    break  # one match per library is enough
        return violations

    @staticmethod
    def _resolve_language(submission_language=None) -> Optional[Language]:
        """Resolve a raw language value into a Language enum member."""
        if submission_language is None:
            return None
        if isinstance(submission_language, Language):
            return submission_language
        # Accept string values like "python", "java", etc.
        for lang in Language:
            if lang.value == str(submission_language).lower():
                return lang
        return None

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer],
                *args, forbidden_imports: List[str] = None,
                submission_language=None, **kwargs) -> TestResult:
        """
        Scan every submission file for forbidden imports.

        Returns score 100 if no forbidden imports are found, 0 otherwise.
        """
        locale = kwargs.get("locale")
        if not forbidden_imports:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("io.forbidden_import.report.no_imports", locale=locale)
            )

        language = self._resolve_language(submission_language)

        if language is None:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.forbidden_import.report.no_lang", locale=locale)
            )

        if not files:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("io.forbidden_import.report.no_files", locale=locale)
            )

        all_violations: List[str] = []
        for submission_file in files:
            found = self._scan_file(
                submission_file.content, forbidden_imports, language
            )
            for lib in found:
                all_violations.append(
                    t("io.forbidden_import.report.violation", locale=locale, lib=lib, file=submission_file.filename)
                )

        if all_violations:
            details = "\n".join(all_violations)
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.forbidden_import.report.failure", locale=locale, details=details)
            )

        return TestResult(
            test_name=self.name,
            score=100.0,
            report=t("io.forbidden_import.report.success", locale=locale)
        )


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
            "forbidden_import": ForbiddenImportTest(),
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
