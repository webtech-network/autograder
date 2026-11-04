"""
Command resolution is owned by the execution evaluators (ARC-03).

The generic grader passes the canonical ``program_command`` verbatim; I/O
evaluators resolve a language map or the ``CMD`` placeholder against the typed
runtime language. No hidden or runtime keyword ever reaches ``execute``.
"""

import pytest
from unittest.mock import MagicMock

from autograder.models.abstract.test_function import EvaluationInput
from autograder.models.contracts.definition import compile_definition, DefinitionValidationError
from autograder.models.dataclass.submission import SubmissionFile
from autograder.template_library.input_output import DontFailTest, ExpectOutputTest
from autograder.template_library.static_analysis import ForbiddenImportTest
from sandbox_manager.models.sandbox_models import CommandResponse, Language, ResponseCategory
from tests.evaluator_calls import invoke


def _session():
    session = MagicMock()
    session.run_commands.return_value = CommandResponse(
        stdout="ok", stderr="", exit_code=0, execution_time=0.1, category=ResponseCategory.SUCCESS)
    return session


def _executed_command(program_command, language=None, function=None):
    session = _session()
    function = function or DontFailTest()
    function.execute(EvaluationInput(language=language, session=session), program_command=program_command)
    return session.run_commands.call_args.kwargs["program_command"]


class TestDictCommandResolution:
    """A language-keyed command map resolves to the submission language."""

    @pytest.mark.parametrize("language,expected", [(Language.PYTHON, "python3 calc.py"), (Language.JAVA, "java Calc")])
    def test_dict_command_resolved_for_language(self, language, expected):
        assert _executed_command({"python": "python3 calc.py", "java": "java Calc"}, language) == expected

    def test_expect_output_resolves_the_same_way(self):
        session = _session()
        ExpectOutputTest().execute(EvaluationInput(language=Language.JAVA, session=session),
                                   program_command={"python": "python3 a.py", "java": "java A"},
                                   expected_output="ok")
        assert session.run_commands.call_args.kwargs["program_command"] == "java A"


class TestCmdPlaceholderResolution:
    """CMD means the conventional per-language default command."""

    @pytest.mark.parametrize("language,expected", [
        (Language.PYTHON, "python3 main.py"), (Language.JAVA, "java Main"), (Language.NODE, "node index.js")])
    def test_cmd_resolved(self, language, expected):
        assert _executed_command("CMD", language) == expected


class TestStringAndMissingLanguage:
    def test_string_command_is_used_directly(self):
        assert _executed_command("python3 my_script.py", Language.PYTHON) == "python3 my_script.py"

    def test_command_unchanged_when_no_language(self):
        assert _executed_command("CMD") == "CMD"


class TestNoHiddenOrRuntimeKeywords:
    """The call shape is strict: configuration keywords only."""

    def test_unknown_keyword_is_rejected(self):
        with pytest.raises(TypeError):
            DontFailTest().execute(EvaluationInput(session=_session()), program_command="CMD",
                                   __submission_language__=Language.PYTHON)

    def test_runtime_language_is_typed_input(self):
        with pytest.raises(TypeError):
            DontFailTest().execute(EvaluationInput(session=_session()), program_command="CMD",
                                   submission_language=Language.PYTHON)


class TestForbiddenImportLanguageInput:
    """ForbiddenImportTest reads the language from its typed input."""

    def setup_method(self):
        self.test_fn = ForbiddenImportTest()

    def test_detects_with_runtime_language(self):
        files = [SubmissionFile("main.py", "import os\n")]
        assert invoke(self.test_fn, files, forbidden_imports=["os"], submission_language=Language.PYTHON).score == 0.0

    def test_clean_file_passes(self):
        files = [SubmissionFile("main.py", "x = 1\n")]
        assert invoke(self.test_fn, files, forbidden_imports=["os"], submission_language=Language.PYTHON).score == 100.0

    def test_no_language_fails_gracefully(self):
        files = [SubmissionFile("main.py", "import os\n")]
        result = invoke(self.test_fn, files, forbidden_imports=["os"])
        assert result.score == 0.0
        assert "language" in result.report.lower()


def test_definition_cannot_supply_runtime_language():
    value = {"schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
             "criteria": {"base": {"weight": 100, "tests": [{"id": "imports", "name": "Imports",
                "type": "forbidden_import", "parameters": {"forbidden_imports": ["os"], "submission_language": "java"}}]}}}
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]["code"] == "RESERVED_PARAMETER"
