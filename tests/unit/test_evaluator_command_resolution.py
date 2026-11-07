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
from tests.process_results import exited
from autograder.models.language import Language
from tests.evaluator_calls import invoke


def _session():
    session = MagicMock()
    session.run_process.return_value = exited("ok")
    return session


def _executed_command(program_command, language=None, function=None):
    session = _session()
    function = function or DontFailTest()
    function.execute(EvaluationInput(language=language, session=session), program_command=program_command)
    return " ".join(session.run_process.call_args.args[0].argv)


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
        assert session.run_process.call_args.args[0].argv == ("java", "A")


class TestCmdPlaceholderResolution:
    """CMD means the conventional per-language default command."""

    @pytest.mark.parametrize("language,expected", [
        (Language.PYTHON, "python3 main.py"), (Language.JAVA, "java Main"), (Language.NODE, "node index.js"),
        (Language.CPP, "./a.out"), (Language.C, "./a.out")])
    def test_cmd_resolved(self, language, expected):
        assert _executed_command("CMD", language) == expected

    def test_default_table_covers_every_domain_language(self):
        """Adding a language without a default would make CMD a compile-time error."""
        from autograder.models.abstract.execution_test import DEFAULT_COMMANDS
        assert set(DEFAULT_COMMANDS) == set(Language)

    def test_cmd_without_default_is_rejected_at_compilation(self, monkeypatch):
        from autograder.models.abstract import execution_test
        monkeypatch.setattr(execution_test, "DEFAULT_COMMANDS", {Language.PYTHON: "python3 main.py"})
        value = {"schema_version": "2.0", "languages": ["python", "java"],
                 "criteria": {"base": {"tests": [{"id": "run", "name": "Run", "type": "dont_fail",
                                                                 "parameters": {"program_command": "CMD"}}]}}}
        with pytest.raises(DefinitionValidationError) as failure:
            compile_definition(value)
        assert failure.value.errors()[0]["code"] == "MISSING_LANGUAGE_COMMAND"


class TestStringAndMissingLanguage:
    def test_string_command_is_used_directly(self):
        assert _executed_command("python3 my_script.py", Language.PYTHON) == "python3 my_script.py"

    def test_string_command_needs_no_language(self):
        assert _executed_command("python3 main.py") == "python3 main.py"

    @pytest.mark.parametrize("command", ["CMD", {"python": "python3 main.py"}])
    def test_language_selected_command_without_a_bound_language_is_an_error(self, command):
        """Never send the unresolved map or the literal placeholder to the process."""
        from autograder.models.evaluation_error import EvaluationError
        with pytest.raises(EvaluationError) as failure:
            _executed_command(command)
        assert failure.value.code == "LANGUAGE_REQUIRED"

    def test_map_alias_keys_are_not_accepted(self):
        """Only canonical identifiers select commands; there is no upper-case alias."""
        value = {"schema_version": "2.0", "languages": ["python"],
                 "criteria": {"base": {"tests": [{"id": "run", "name": "Run", "type": "dont_fail",
                                                                 "parameters": {"program_command": {"PYTHON": "python3 main.py"}}}]}}}
        with pytest.raises(DefinitionValidationError):
            compile_definition(value)


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
    value = {"schema_version": "2.0", "languages": ["python"],
             "criteria": {"base": {"tests": [{"id": "imports", "name": "Imports",
                "type": "forbidden_import", "parameters": {"forbidden_imports": ["os"], "submission_language": "java"}}]}}}
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]["code"] == "RESERVED_PARAMETER"


def test_execution_evaluator_without_a_program_command_parameter_compiles():
    """``BaseExecutionTest`` only checks ``program_command`` when an evaluator takes one."""
    from typing import Annotated
    from pydantic import Field
    from autograder import BaseExecutionTest, Template
    from autograder.models.dataclass.test_result import TestResult

    class RunsEntryPoint(BaseExecutionTest):
        name = "runs_entry_point"
        description = "Runs a fixed entry point."

        def execute(self, evaluation, *, marker: Annotated[str, Field(min_length=1)]):  # pylint: disable=arguments-differ
            return TestResult(self.name, 100, marker)

    evaluator = RunsEntryPoint()
    assert list(evaluator.validate_parameters({"marker": "x"}, languages=("python", "java"))) == []
    definition = {
        "schema_version": "2.0", "languages": ["python", "java"],
        "criteria": {"base": {"tests": [{
            "id": "runs", "type": "runs_entry_point", "name": "Runs", "parameters": {"marker": "x"}}]}},
    }
    compiled = compile_definition(definition, templates={"local": Template("Local", "Local", [evaluator])})
    assert compiled.definition.criteria.base.tests[0].parameters == {"marker": "x"}
