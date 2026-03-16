"""
Tests verifying that command resolution happens inside GraderService.process_test()
and that no hidden __submission_language__ kwarg ever reaches a test's execute().

These are pure-unit tests — no sandbox or real submission required.
"""

import pytest
from typing import List
from unittest.mock import MagicMock

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
    svc = GraderService()
    if language:
        svc.set_submission_language(language)
    return svc


def _make_test_node(params: dict, fn: TestFunction = None) -> TestNode:
    if fn is None:
        fn = RecordingTestFunction()
    return TestNode(name="test", test_function=fn, parameters=params)


# ---------------------------------------------------------------------------
# 1. program_command dict is resolved before execute() is called
# ---------------------------------------------------------------------------

class TestDictCommandResolutionInProcessTest:

    def test_dict_command_resolved_for_python(self):
        svc = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "python3 calc.py"

    def test_dict_command_resolved_for_java(self):
        svc = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "java Calc"

    def test_dict_command_missing_language_gives_none(self):
        """When language is not in the dict, resolved value is None."""
        svc = _make_grader(Language.NODE)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {
                "python": "python3 calc.py",
                "java": "java Calc",
            }
        }, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] is None


# ---------------------------------------------------------------------------
# 2. CMD placeholder is resolved before execute()
# ---------------------------------------------------------------------------

class TestCmdPlaceholderResolution:

    def test_cmd_resolved_for_python(self):
        svc = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "python3 main.py"

    def test_cmd_resolved_for_java(self):
        svc = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "java Main"

    def test_cmd_resolved_for_node(self):
        svc = _make_grader(Language.NODE)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "node index.js"


# ---------------------------------------------------------------------------
# 3. Legacy string commands pass through unchanged
# ---------------------------------------------------------------------------

class TestLegacyStringPassthrough:

    def test_string_command_is_not_modified(self):
        svc = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "python3 my_script.py"}, fn)

        svc.process_test(node)

        # Legacy strings bypass the resolver and are forwarded as-is
        assert fn.recorded_kwargs["program_command"] == "python3 my_script.py"


# ---------------------------------------------------------------------------
# 4. Without a language set, dict/CMD commands are left unchanged
# ---------------------------------------------------------------------------

class TestNoLanguageNoResolution:

    def test_dict_unchanged_when_no_language(self):
        """Without language, dict program_command is left as-is (resolver not called)."""
        svc = _make_grader()          # no language
        fn = RecordingTestFunction()
        cmd_dict = {"python": "python3 calc.py"}
        node = _make_test_node({"program_command": cmd_dict}, fn)

        svc.process_test(node)

        # Dict should reach execute() untouched — resolution was skipped
        assert fn.recorded_kwargs["program_command"] == cmd_dict

    def test_cmd_unchanged_when_no_language(self):
        svc = _make_grader()
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node)

        assert fn.recorded_kwargs["program_command"] == "CMD"


# ---------------------------------------------------------------------------
# 5. The hidden __submission_language__ kwarg NEVER reaches execute()
# ---------------------------------------------------------------------------

class TestNoHiddenKwarg:

    def test_no_hidden_kwarg_with_language_set(self):
        """Even when language is set, __submission_language__ must not appear in execute()."""
        svc = _make_grader(Language.PYTHON)
        fn = RecordingTestFunction()
        node = _make_test_node({"program_command": "CMD"}, fn)

        svc.process_test(node)

        assert "__submission_language__" not in fn.recorded_kwargs

    def test_no_hidden_kwarg_without_language(self):
        svc = _make_grader()
        fn = RecordingTestFunction()
        node = _make_test_node({}, fn)

        svc.process_test(node)

        assert "__submission_language__" not in fn.recorded_kwargs

    def test_no_hidden_kwarg_with_dict_command(self):
        svc = _make_grader(Language.JAVA)
        fn = RecordingTestFunction()
        node = _make_test_node({
            "program_command": {"python": "python3 a.py", "java": "java A"}
        }, fn)

        svc.process_test(node)

        assert "__submission_language__" not in fn.recorded_kwargs


# ---------------------------------------------------------------------------
# 6. ForbiddenImportTest with declared submission_language param
# ---------------------------------------------------------------------------

class TestForbiddenImportDeclaredParam:

    def setup_method(self):
        self.test_fn = ForbiddenImportTest()

    def test_works_with_declared_language_enum(self):
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 0.0

    def test_works_with_declared_language_string(self):
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language="python",
        )
        assert result.score == 0.0

    def test_clean_file_passes(self):
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
