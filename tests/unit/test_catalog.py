"""Discovery must resolve and validate through the real compilation contract."""
from copy import deepcopy
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from autograder import compile_definition, describe_templates, DefinitionValidationError
from autograder.models.contracts.catalog import describe_template
from autograder.services.template_library_service import TemplateLibraryService
from examples.contracts.custom_evaluator import ContainsText, DEFINITION, TrustedTextTemplate


@pytest.mark.parametrize("template", describe_templates().templates, ids=lambda item: item.identifier)
def test_every_catalog_evaluator_resolves_and_its_sample_compiles(template):
    instance = TemplateLibraryService.get_instance().start_template(template.identifier)
    assert {item.identifier for item in template.evaluators} == set(instance.get_tests())
    for evaluator in template.evaluators:
        function = instance.get_test(evaluator.identifier)
        assert evaluator.parameters_schema == {
            **function.config_schema.model_json_schema(), "additionalProperties": False}
        for language in evaluator.supported_languages or ["python", "java", "node", "cpp", "c"]:
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
    assert evaluators["health_check"].required_capabilities == ["http_network", "sandbox_execution"]
    assert evaluators["expect_output"].required_capabilities == ["sandbox_execution"]
    assert evaluators["forbidden_import"].supported_languages == ["python", "java", "node", "cpp", "c"]
    assert evaluators["has_tag"].supported_languages is None
    for evaluator in evaluators.values():
        for capability in evaluator.required_capabilities:
            assert catalog.capabilities[capability]
    assert "local sandbox pool does not" in catalog.capabilities["http_network"]


def test_trusted_override_is_local_to_call_and_uses_same_resolution_as_compiler():
    custom = TrustedTextTemplate()
    catalog = describe_templates({"webdev": custom})
    assert next(t for t in catalog.templates if t.identifier == "webdev").evaluators[0].identifier == "contains_text"
    value = deepcopy(DEFINITION)
    value["templates"] = ["webdev"]
    assert compile_definition(value, templates={"webdev": custom}).templates == [custom]
    assert "has_tag" in TemplateLibraryService.get_instance().start_template("webdev").get_tests()


def test_explicit_examples_are_validated_and_normalized():
    class Parameters(BaseModel):
        needle: str = Field(pattern="^hello$")
        mode: Literal["literal"] = "literal"

    evaluator = ContainsText()
    evaluator.config_schema = Parameters
    custom = TrustedTextTemplate()
    custom.tests = {evaluator.name: evaluator}
    with pytest.raises(ValueError, match="example_parameters"):
        describe_template("custom", custom)
    evaluator.example_parameters = {"needle": "hello"}
    assert describe_template("custom", custom).evaluators[0].sample_parameters == {"needle": "hello", "mode": "literal"}


@pytest.mark.parametrize("invalid", [object(), {"source": "print('not a plugin')"}, TrustedTextTemplate])
def test_python_extension_requires_an_instantiated_template(invalid):
    with pytest.raises(DefinitionValidationError) as error:
        compile_definition(DEFINITION, templates={"trusted_text": invalid})
    assert error.value.errors()[0]["code"] == "INVALID_TEMPLATE"
    with pytest.raises(TypeError, match="Template instances"):
        describe_template("trusted_text", invalid)
