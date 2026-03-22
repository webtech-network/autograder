"""
Tests verifying that command resolution happens inside GraderService.process_test()
and that no hidden __submission_language__ kwarg ever reaches a test's execute().

These are pure-unit tests — no sandbox or real submission required.
"""

from typing import List

from autograder.services.grader_service import GraderService
from autograder.models.criteria_tree import TestNode
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library.input_output import ForbiddenImportTest
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.models.sandbox_models import Language


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class RecordingTestFunction(TestFunction):
    """A test function that records the exact kwargs it was called with."""

    def __init__(self):
        self.recorded_kwargs = None

    @property
    def name(self):
        return "recording_test"

    @property
    def description(self):
        return "Records kwargs for assertion in tests."

    @property
    def parameter_description(self) -> List[ParamDescription]:
        return []

    def execute(self, files, sandbox, *args, **kwargs):
        self.recorded_kwargs = dict(kwargs)
        return TestResult(test_name=self.name, score=100.0, report="ok")


def _make_grader(language=None) -> GraderService:
    return GraderService(), language


def _make_test_node(params: dict, fn: TestFunction = None) -> TestNode:
    if fn is None:
        fn = RecordingTestFunction()
    return TestNode(name="test", test_function=fn, parameters=params)


# ---------------------------------------------------------------------------
# 1. program_command dict is resolved before execute() is called
# ---------------------------------------------------------------------------

class TestDictCommandResolutionInProcessTest:
    """Test resolution of standard format dictionary commands during grader test processing."""

    def test_dict_command_resolved_for_python(self):
        """Test proper dict resolution for Python language."""
        svc, language = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "python3 calc.py"

    def test_dict_command_resolved_for_java(self):
        """Test proper dict resolution for Java language."""
        svc, language = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "java Calc"

    def test_dict_command_missing_language_gives_none(self):
        """When language is not in the dict, resolved value is None."""
        svc, language = _make_grader(Language.NODE)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] is None


# ---------------------------------------------------------------------------
# 2. CMD placeholder is resolved before execute()
# ---------------------------------------------------------------------------

class TestCmdPlaceholderResolution:
    """Test resolution of CMD placeholder commands during grader test processing."""

    def test_cmd_resolved_for_python(self):
        """Test CMD placeholder resolves appropriately for Python."""
        svc, language = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "python3 main.py"

    def test_cmd_resolved_for_java(self):
        """Test CMD placeholder resolves appropriately for Java."""
        svc, language = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "java Main"

    def test_cmd_resolved_for_node(self):
        """Test CMD placeholder resolves appropriately for Node.js."""
        svc, language = _make_grader(Language.NODE)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "node index.js"


# ---------------------------------------------------------------------------
# 3. Invalid formats handled
# ---------------------------------------------------------------------------

class TestInvalidFormatHandled:
    """Test grader handling of invalid command formats."""

    def test_invalid_string_command_is_none(self):
        """Test non-CMD single strings fall back to None directly."""
        svc, language = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "python3 my_script.py"}, fn)

        svc.process_test(node, submission_language=language)

        # Non-CMD strings are invalid without legacy fallback, returning None
        assert fn.recorded_kwargs["program_command"] is None


# ---------------------------------------------------------------------------
# 4. Without a language set, dict/CMD commands are left unchanged
# ---------------------------------------------------------------------------

class TestNoLanguageNoResolution:
    """Test standard formats gracefully do-nothing if no submission language is present."""

    def test_dict_unchanged_when_no_language(self):
        """Without language, dict program_command is left as-is (resolver not called)."""
        svc, language = _make_grader()          # no language
        fn = RecordingTestFunction()
        cmd_dict = {"python": "python3 calc.py"}
        node = _make_test_node({"program_command": cmd_dict}, fn)

        svc.process_test(node, submission_language=language)

        # Dict should reach execute() untouched — resolution was skipped
        assert fn.recorded_kwargs["program_command"] == cmd_dict

    def test_cmd_unchanged_when_no_language(self):
        """Without language, CMD placeholder is unchanged (resolver not called)."""
        svc, language = _make_grader()
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node, submission_language=language)

        assert fn.recorded_kwargs["program_command"] == "CMD"


# ---------------------------------------------------------------------------
# 5. The hidden __submission_language__ kwarg NEVER reaches execute()
# ---------------------------------------------------------------------------

class TestNoHiddenKwarg:
    """Test no internal kwargs magically pass into execution function kwargs."""

    def test_no_hidden_kwarg_with_language_set(self):
        """Even when language is set, __submission_language__ must not appear in execute()."""
        svc, language = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node, submission_language=language)

        assert "__submission_language__" not in fn.recorded_kwargs

    def test_no_hidden_kwarg_without_language(self):
        """Hidden kwarg shouldn't appear even if there is no language to configure."""
        svc, language = _make_grader()
        fn = RecordingTestFunction()
        node = _make_test_node({}, fn)

        svc.process_test(node, submission_language=language)

        assert "__submission_language__" not in fn.recorded_kwargs

    def test_no_hidden_kwarg_with_dict_command(self):
        """Hidden kwarg shouldn't appear even if there is a dict correctly configured."""
        svc, language = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {"python": "python3 a.py", "java": "java A"}
        }, fn)

        svc.process_test(node, submission_language=language)

        assert "__submission_language__" not in fn.recorded_kwargs


# ---------------------------------------------------------------------------
# 6. ForbiddenImportTest with declared submission_language param
# ---------------------------------------------------------------------------

class TestForbiddenImportDeclaredParam:
    """Test functionality of ForbiddenImportTest with its declared parameters."""

    test_fn: ForbiddenImportTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()

    def test_works_with_declared_language_enum(self):
        """Test forbidden imports with standard language enum string."""
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 0.0

    def test_works_with_declared_language_string(self):
        """Test forbidden imports with standard bare language string."""
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language="python",
        )
        assert result.score == 0.0

    def test_clean_file_passes(self):
        """Test clean file accurately passes forbidden imports testing."""
        files = [SubmissionFile("main.py", "x = 1\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 100.0

    def test_no_language_fails_gracefully(self):
        """Missing submission_language should return score 0 with a helpful message."""
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
        )
        assert result.score == 0.0
        assert "language" in result.report.lower()

    def test_hidden_kwarg_is_not_accepted(self):
        """Confirm the old hidden kwarg name no longer works (absorbed by **kwargs, language=None)."""
        files = [SubmissionFile("main.py", "import os\n")]
        # __submission_language__ goes into **kwargs and is ignored → language resolves to None
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            __submission_language__=Language.PYTHON,  # old name — must be silently ignored
        )
        # Language will be None → score 0 because it can't determine scan patterns
        assert result.score == 0.0
