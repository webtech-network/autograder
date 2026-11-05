"""Discovery must resolve and validate through the real compilation contract."""
from copy import deepcopy
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from autograder import (
    EvaluationInput, HostCapabilities, Submission, SubmissionFile, Template, TestFunction, TestResult,
    compile_definition, describe_templates, evaluate_submission, DefinitionValidationError,
)
from autograder.models.language import LANGUAGE_IDS
from autograder.models.contracts.catalog import describe_template
from autograder.template_library import BUILTIN_TEMPLATES
from examples.contracts.custom_evaluator import ContainsText, DEFINITION, TEMPLATE
from tests.builtin_evaluator_cases import leaves


@pytest.mark.parametrize("template", describe_templates().templates, ids=lambda item: item.identifier)
def test_every_catalog_evaluator_resolves_and_its_sample_compiles(template):
    instance = BUILTIN_TEMPLATES[template.identifier]
    assert {item.identifier for item in template.evaluators} == set(instance.get_tests())
    for evaluator in template.evaluators:
        function = instance.get_test(evaluator.identifier)
        assert evaluator.parameters_schema == {
            **function.config_schema.model_json_schema(), "additionalProperties": False}
        for language in evaluator.supported_languages or LANGUAGE_IDS:
            value = deepcopy(DEFINITION)
            value.update(templates=[template.identifier], languages=[language])
            value["criteria"]["base"]["tests"][0].update(
                type=evaluator.identifier, parameters=evaluator.sample_parameters)
            compiled = compile_definition(value)
            assert compiled.criteria_tree.base.get_all_tests()[0].test_function is function


def test_capabilities_are_per_evaluator_and_explain_host_limits():
    catalog = describe_templates()
    evaluators = {e.identifier: e for t in catalog.templates for e in t.evaluators}
    assert evaluators["forbidden_import"].required_capabilities == []
    assert evaluators["forbidden_keyword"].required_capabilities == ["structural_analysis"]
    assert evaluators["ai_sorting_algorithm"].required_capabilities == ["ai_provider"]
    assert evaluators["health_check"].required_capabilities == ["http_network"]
    assert evaluators["expect_output"].required_capabilities == ["sandbox_execution"]
    assert evaluators["forbidden_import"].supported_languages == ["python", "java", "node", "cpp", "c"]
    assert evaluators["has_tag"].supported_languages is None
    for evaluator in evaluators.values():
        for capability in evaluator.required_capabilities:
            assert catalog.capabilities[capability]
    assert "supplies no server lifecycle" in catalog.capabilities["http_network"]


def test_trusted_override_is_local_to_call_and_uses_same_resolution_as_compiler():
    custom = TEMPLATE
    catalog = describe_templates({"webdev": custom})
    assert next(t for t in catalog.templates if t.identifier == "webdev").evaluators[0].identifier == "contains_text"
    value = deepcopy(DEFINITION)
    value["templates"] = ["webdev"]
    assert dict(compile_definition(value, templates={"webdev": custom}).templates) == {"webdev": custom}
    assert "has_tag" in BUILTIN_TEMPLATES["webdev"].get_tests()


def test_explicit_examples_are_validated_and_normalized():
    class Parameters(BaseModel):
        needle: str = Field(pattern="^hello$")
        mode: Literal["literal"] = "literal"

    class ConstrainedText(ContainsText):
        config_schema = Parameters

        def execute(self, evaluation, *, needle, mode="literal"):  # pylint: disable=arguments-differ
            return super().execute(evaluation, needle=needle)

    evaluator = ConstrainedText()
    custom = Template("Trusted text", "One local, trusted evaluator", [evaluator])
    with pytest.raises(ValueError, match="example_parameters"):
        describe_template("custom", custom)
    evaluator.example_parameters = {"needle": "hello"}
    assert describe_template("custom", custom).evaluators[0].sample_parameters == {"needle": "hello", "mode": "literal"}


@pytest.mark.parametrize("invalid", [object(), {"source": "print('not a plugin')"}, Template])
def test_python_extension_requires_an_instantiated_template(invalid):
    with pytest.raises(DefinitionValidationError) as error:
        compile_definition(DEFINITION, templates={"trusted_text": invalid})
    assert error.value.errors()[0]["code"] == "INVALID_TEMPLATE"
    with pytest.raises(TypeError, match="Template instances"):
        describe_template("trusted_text", invalid)


# --- Capabilities are declared once, on the evaluator (ONB-08) ------------------

class StaticCheck(TestFunction):
    name = "static_check"
    description = "Reads the selected files only."

    def execute(self, evaluation: EvaluationInput) -> TestResult:
        return TestResult(self.name, 100, f"session={evaluation.session is not None}")


class RunsProgram(TestFunction):
    name = "runs_program"
    description = "Runs the program in the bound session."
    required_capabilities = ("sandbox_execution",)

    def execute(self, evaluation: EvaluationInput) -> TestResult:
        return TestResult(self.name, 100, f"session={evaluation.session is not None}")


def mixed_template():
    """An execution template that also holds a static evaluator."""
    return Template("Mixed", "Static and execution evaluators", [StaticCheck(), RunsProgram()])


def test_discovery_capabilities_come_only_from_evaluators_including_mixed_templates():
    catalog = describe_templates({"mixed": mixed_template()})
    for template in catalog.templates:
        assert "requires_sandbox" not in template.model_dump()
        instance = BUILTIN_TEMPLATES.get(template.identifier) or mixed_template()
        for evaluator in template.evaluators:
            assert "requires_sandbox" not in evaluator.model_dump()
            declared = instance.get_test(evaluator.identifier).required_capabilities
            assert evaluator.required_capabilities == sorted(set(declared)), evaluator.identifier
    [mixed] = [t for t in catalog.templates if t.identifier == "mixed"]
    assert {e.identifier: e.required_capabilities for e in mixed.evaluators} == {
        "static_check": [], "runs_program": ["sandbox_execution"]}


class FakeSession:
    """The ExecutionSession protocol, recording staging and closing only."""
    fixture_root = "/fixtures"

    def __init__(self):
        self.staged, self.closed = None, 0

    def prepare_workdir(self, files):
        self.staged = dict(files)

    def stage_fixture(self, path, content, read_only):
        raise AssertionError("no fixtures are declared")

    def run_process(self, request):
        raise AssertionError("no process is run")

    def read_artifact(self, path):
        raise FileNotFoundError(path)

    def close(self):
        self.closed += 1


def run_mixed(*evaluators):
    sessions = []

    def acquire(language):
        sessions.append(FakeSession())
        return sessions[-1]

    definition = {"schema_version": "1.0", "templates": ["mixed"], "languages": ["python"],
                  "criteria": {"base": {"weight": 100, "tests": [
                      {"id": name, "type": name, "name": name, "parameters": {}} for name in evaluators]}}}
    outcome = evaluate_submission(
        Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "print(1)")}),
        definition=definition, templates={"mixed": mixed_template()},
        capabilities=HostCapabilities(execution=acquire))
    return outcome, sessions


def test_static_evaluator_in_an_execution_template_acquires_no_session():
    outcome, sessions = run_mixed("static_check")
    assert outcome.status == "completed" and outcome.score == 100
    assert sessions == []
    assert leaves(outcome.model_dump(mode="json")["tree"]) == {"static_check": [100, "session=False"]}


def test_execution_evaluator_alone_acquires_and_receives_the_session():
    outcome, sessions = run_mixed("static_check", "runs_program")
    assert outcome.status == "completed"
    [session] = sessions
    assert session.closed == 1 and set(session.staged) == {"main.py"}
    assert leaves(outcome.model_dump(mode="json")["tree"]) == {
        "static_check": [100, "session=False"], "runs_program": [100, "session=True"]}


def test_one_builtin_registry_backs_discovery_and_compilation():
    import importlib
    assert [t.identifier for t in describe_templates().templates] == list(BUILTIN_TEMPLATES)
    assert list(BUILTIN_TEMPLATES) == ["webdev", "api", "input_output", "static_analysis"]
    assert all(template.template_name for template in BUILTIN_TEMPLATES.values())
    with pytest.raises(TypeError):
        BUILTIN_TEMPLATES["local"] = TEMPLATE  # the registry is read-only; inject per call instead
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("autograder.services.template_library_service")
    import autograder.template_library as library
    assert library.__all__ == ["BUILTIN_TEMPLATES"]
