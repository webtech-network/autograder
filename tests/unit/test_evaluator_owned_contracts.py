"""ARC-03: evaluator validation and execution rules live inside each evaluator.

The generic compiler does not interpret parameter names, constraints come only
from the evaluator's contract, and every evaluator is invoked through one
validated call shape: ``execute(evaluation, *, <normalized configuration>)``.
"""
import inspect
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ConfigDict, Field

from autograder import (
    AiTestFunction, DefinitionValidationError, EvaluationInput, HostCapabilities, Submission,
    SubmissionFile, Template, TestFunction, TestResult, build_pipeline, compile_definition,
    describe_templates, evaluate_submission,
)
from autograder.models.contracts import definition as definition_module
from tests.process_results import exited
from autograder.models.language import Language
from tests.grading import FakeProvider


def template_with(*evaluators, sandbox=False):
    class Local(Template):
        template_name = "Local"
        template_description = "Trusted local evaluators."
        requires_sandbox = sandbox

        def __init__(self):
            self.tests = {evaluator.name: evaluator for evaluator in evaluators}
    return Local()


def definition(evaluator, parameters, languages=("python",), templates=("local",), extra_tests=()):
    return {"schema_version": "1.0", "templates": list(templates), "languages": list(languages),
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": "check", "type": evaluator, "name": "Check", "parameters": parameters}, *extra_tests]}}}


def submission(files=None, language=None):
    files = files or {"main.py": "print('secret')"}
    return Submission("u", "u", "a", {name: SubmissionFile(name, content) for name, content in files.items()},
                      language=language)


def errors(value, **templates):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value, templates=templates)
    return failure.value.errors()


# --- The compiler has no evaluator-specific branches -------------------------

def test_generic_compiler_contains_no_evaluator_specific_parameter_names():
    source = inspect.getsource(definition_module)
    for name in ("program_command", "forbidden_keywords", "custom_ast_grep_rules", "ForbiddenKeywordTest", "ast_grep"):
        assert name not in source


class CheckText(TestFunction):
    """A plain-text evaluator reusing parameter names of built-in evaluators."""
    name = "check_text"
    description = "Fail when any forbidden word appears in plain text."

    def execute(self, evaluation: EvaluationInput, *, forbidden_keywords: list[str],
                program_command: dict[str, str], custom_ast_grep_rules: list[str]) -> TestResult:
        found = [word for word in forbidden_keywords for file in evaluation.files if word in file.content]
        return TestResult(self.name, 0 if found else 100, f"found={found} command={program_command}")


def test_same_parameter_name_does_not_inherit_another_evaluators_rules():
    value = definition("check_text", {"forbidden_keywords": ["secret"], "program_command": {"java": "x"},
                                      "custom_ast_grep_rules": ["not an ast rule"]}, languages=("python", "node"))
    compiled = compile_definition(value, templates={"local": template_with(CheckText())})
    outcome = evaluate_submission(submission(language=Language.PYTHON), definition=compiled)
    assert outcome.status == "completed"
    assert outcome.score == 0
    assert "found=['secret']" in outcome.tree.base.tests[0].report


@pytest.mark.parametrize("parameters,code,path", [
    ({"forbidden_keywords": ["secret"]}, "UNSUPPORTED_KEYWORD", ["forbidden_keywords", 0]),
    ({"forbidden_keywords": ["eval_call"]}, "UNSUPPORTED_KEYWORD", ["forbidden_keywords", 0]),
    ({"custom_ast_grep_rules": [{"unknown": 1}]}, "INVALID_AST_RULE", ["custom_ast_grep_rules", 0]),
    ({"custom_ast_grep_rules": [{"kind": 3}]}, "INVALID_AST_RULE", ["custom_ast_grep_rules", 0]),
])
def test_builtin_structural_semantics_are_evaluator_owned(parameters, code, path):
    value = definition("forbidden_keyword", parameters, languages=("python", "java"), templates=("static_analysis",))
    [error] = errors(value)
    assert error["code"] == code
    assert error["path"] == ["criteria", "base", "tests", 0, "parameters", *path]


def test_builtin_command_coverage_is_evaluator_owned():
    value = definition("expect_output", {"program_command": {"python": "python3 main.py"}, "expected_output": "x"},
                       languages=("python", "java"), templates=("input_output",))
    [error] = errors(value)
    assert error["code"] == "MISSING_LANGUAGE_COMMAND"
    assert error["path"][-2:] == ["parameters", "program_command"]


def test_validation_hook_receives_an_isolated_copy_and_allowed_languages():
    seen = []

    class Hooked(TestFunction):
        name = "hooked"
        description = "Hook recorder."

        def validate_parameters(self, parameters, *, languages):
            seen.append((deepcopy(parameters), languages))
            parameters["items"].append("mutated")
            return ()

        def execute(self, evaluation, *, items: list[str]):
            return TestResult(self.name, 100, ",".join(items))

    compiled = compile_definition(definition("hooked", {"items": ["a"]}, languages=("python", "c")),
                                  templates={"local": template_with(Hooked())})
    assert seen == [({"items": ["a"]}, ("python", "c"))]
    assert compiled.criteria_tree.base.tests[0].parameters["items"] == ("a",)


# --- Constraints come only from the evaluator contract ------------------------

class Plain(TestFunction):
    name = "plain"
    description = "Ordinary Python types invent no constraints."

    def execute(self, evaluation, *, offset: int, label: str, note: str = "") -> TestResult:
        return TestResult(self.name, 100, f"{offset}|{label}|{note}")


class Constrained(TestFunction):
    name = "constrained"
    description = "Explicit Annotated constraints are enforced."

    def execute(self, evaluation, *, offset: Annotated[int, Field(ge=0)],
                label: Annotated[str, Field(min_length=1)]) -> TestResult:
        return TestResult(self.name, 100, f"{offset}|{label}")


def test_negative_integer_and_empty_string_are_legal_without_explicit_constraints():
    template = template_with(Plain())
    outcome = evaluate_submission(submission(), definition=definition("plain", {"offset": -1, "label": ""}),
                                  templates={"local": template})
    assert outcome.status == "completed"
    assert outcome.tree.base.tests[0].report == "-1||"
    assert outcome.tree.base.tests[0].parameters == {"offset": -1, "label": "", "note": ""}
    schema = Plain().config_schema.model_json_schema()
    assert schema["required"] == ["offset", "label"]
    assert "minimum" not in schema["properties"]["offset"] and "minLength" not in schema["properties"]["label"]


@pytest.mark.parametrize("parameters,field", [({"offset": -1, "label": "x"}, "offset"), ({"offset": 0, "label": ""}, "label")])
def test_explicitly_constrained_variants_are_rejected(parameters, field):
    [error] = errors(definition("constrained", parameters), local=template_with(Constrained()))
    assert error["path"][-2:] == ["parameters", field]


def test_explicitly_constrained_values_inside_bounds_are_accepted():
    compiled = compile_definition(definition("constrained", {"offset": 0, "label": "x"}),
                                  templates={"local": template_with(Constrained())})
    assert dict(compiled.criteria_tree.base.tests[0].parameters) == {"offset": 0, "label": "x"}


# --- One validated call shape -------------------------------------------------

class Needle(TestFunction):
    """The issue's example: an ordinary annotated method with no **kwargs."""
    name = "needle"
    description = "Find a needle."

    def execute(self, evaluation, *, needle: str):
        found = any(needle in file.content for file in evaluation.files)
        return TestResult(self.name, 100 if found else 0, "found" if found else "missing")


def test_ordinary_annotated_evaluator_without_kwargs_compiles_and_runs():
    outcome = evaluate_submission(submission(), definition=definition("needle", {"needle": "secret"}),
                                  templates={"local": template_with(Needle())})
    assert outcome.status == "completed" and outcome.score == 100


class LegacyShape(TestFunction):
    name = "legacy"
    description = "Old files/sandbox shape."

    def execute(self, files, sandbox, *, needle: str):  # pylint: disable=arguments-differ
        return TestResult(self.name, 100, "")


class SwallowsKwargs(TestFunction):
    name = "swallows"
    description = "Collects arbitrary runtime values."

    def execute(self, evaluation, *, needle: str, **kwargs):
        return TestResult(self.name, 100, "")


class Unannotated(TestFunction):
    name = "unannotated"
    description = "Missing annotation."

    def execute(self, evaluation, *, needle):
        return TestResult(self.name, 100, "")


class Mismatched(TestFunction):
    name = "mismatched"
    description = "Explicit contract disagrees with execute."

    class Parameters(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        needle: str
        other: int = 0

    config_schema = Parameters

    def execute(self, evaluation, *, needle: str):
        return TestResult(self.name, 100, "")


class ReservedName(TestFunction):
    name = "reserved"
    description = "Configuration named like runtime context."

    def execute(self, evaluation, *, locale: str):
        return TestResult(self.name, 100, "")


class AiWithKwargs(AiTestFunction):
    name = "ai_kwargs"
    description = "Prompt builder with kwargs."

    def build_prompt(self, evaluation, **kwargs):
        return "prompt"


@pytest.mark.parametrize("evaluator,message", [
    (LegacyShape(), "execute(self, evaluation, *, <parameters>)"),
    (SwallowsKwargs(), "**kwargs"),
    (Unannotated(), "annotate"),
    (Mismatched(), "must match its parameter contract"),
    (ReservedName(), "reserved runtime names"),
    (AiWithKwargs(), "build_prompt(self, evaluation, *, <parameters>)"),
])
def test_invalid_signatures_fail_at_compilation_and_registration(evaluator, message):
    error, *_ = errors(definition(evaluator.name, {"needle": "x"}), local=template_with(evaluator))
    assert error["code"] == "INVALID_TEMPLATE"
    assert message in error["message"]
    with pytest.raises(TypeError, match=message.replace("*", r"\*").replace("(", r"\(").replace(")", r"\)")):
        describe_templates({"local": template_with(evaluator)})


# --- Runtime input: only what an evaluator uses --------------------------------

class Capture(TestFunction):
    name = "capture"
    description = "Record the typed runtime input."

    def __init__(self):
        self.calls = []

    def execute(self, evaluation):
        self.calls.append(evaluation)
        return TestResult(self.name, 100, "ok")


class Review(AiTestFunction):
    name = "review"
    description = "AI review."

    def build_prompt(self, evaluation, *, focus: str = "clarity"):
        return f"Review {focus}"


def Provider():  # pylint: disable=invalid-name
    return FakeProvider(score=50)


def test_ordinary_evaluators_receive_no_ai_results_provider_or_scope():
    capture = Capture()
    value = definition("capture", {}, extra_tests=[{"id": "ai", "type": "review", "name": "AI", "parameters": {}}])
    outcome = evaluate_submission(submission(), definition=value, templates={"local": template_with(capture, Review())},
                                  capabilities=HostCapabilities(ai=Provider()))
    assert outcome.status == "completed"
    assert [test.score for test in outcome.tree.base.tests] == [100, 50]
    [evaluation] = capture.calls
    assert set(vars(evaluation)) == {"files", "language", "locale", "session"}
    assert evaluation.session is None and evaluation.language == Language.PYTHON


def test_execution_session_is_bound_only_to_evaluators_that_declare_it():
    session = MagicMock()
    session.run_process.return_value = exited("ok")
    capture = Capture()
    value = definition("capture", {}, templates=("local", "input_output"), extra_tests=[{
        "id": "run", "type": "expect_output", "name": "Run",
        "parameters": {"program_command": "CMD", "expected_output": "ok"}}])
    outcome = evaluate_submission(submission(), definition=value, templates={"local": template_with(capture)},
                                  capabilities=HostCapabilities(execution=lambda language: session))
    assert outcome.status == "completed" and outcome.score == 100
    assert capture.calls[0].session is None
    assert session.run_process.call_args.args[0].argv == ("python3", "main.py")
    session.close.assert_called_once()


def test_shared_stateless_evaluator_serves_concurrent_runs_independently():
    pipeline = build_pipeline(definition=definition("needle", {"needle": "secret"}),
                              templates={"local": template_with(Needle())})
    contents = ["secret", "nothing"] * 8
    with ThreadPoolExecutor(max_workers=4) as pool:
        scores = list(pool.map(lambda text: pipeline.run(submission({"main.py": text})).outcome.score, contents))
    assert scores == [100, 0] * 8


# --- A new evaluator is a local change ----------------------------------------

def test_new_trusted_evaluator_needs_only_implementation_contract_and_registration():
    from examples.contracts.custom_evaluator import DEFINITION, TrustedTextTemplate, grade
    catalog = describe_templates({"trusted_text": TrustedTextTemplate()})
    [template] = [item for item in catalog.templates if item.identifier == "trusted_text"]
    [evaluator] = template.evaluators
    assert evaluator.identifier == "contains_text"
    assert evaluator.parameters_schema["properties"]["needle"]["description"] == "Text to find"
    assert evaluator.parameters_schema["required"] == ["needle"]
    assert compile_definition(DEFINITION, templates={"trusted_text": TrustedTextTemplate()}).definition_hash
    assert grade("<h1>Hello</h1>").score == 100
    assert grade("<h1>Bye</h1>").score == 0
