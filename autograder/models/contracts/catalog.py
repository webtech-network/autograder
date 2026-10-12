"""Typed evaluator catalog derived from the executable parameter contracts.

The catalog never keeps a second registry of prose or schemas: every field is
read from the trusted ``Template``/``TestFunction`` instances that
``compile_definition`` uses, so discovery and validation cannot drift.
"""
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.contracts.parameters import LanguageId

Capability = Literal["sandbox_execution", "http_network", "ai_provider", "structural_analysis"]

CAPABILITY_DESCRIPTIONS: Dict[str, str] = {
    "sandbox_execution": "Runs the submission through a host-supplied execution session. Unavailable without execution support for the selected language.",
    "http_network": "Requires a host-supplied assessed-server session covering startup, readiness, HTTP reachability and teardown. The default Docker profile fails before acquisition because it supplies no server lifecycle.",
    "ai_provider": "Delegates assessment to a host-supplied AI provider. Missing provider support fails the execution before scoring.",
    "structural_analysis": "Uses in-process ast-grep structural analysis of the submission source. Requires ast-grep-py to be installed and a supported language; missing analysis fails the assessment instead of scoring zero.",
}


class EvaluatorDescription(BaseModel):
    """One evaluator, as accepted by criterion ``type`` within its template."""
    model_config = ConfigDict(extra="forbid")
    identifier: str
    description: str
    parameters_schema: Dict[str, Any]
    sample_parameters: Dict[str, Any]
    required_capabilities: List[Capability]
    supported_languages: Optional[List[LanguageId]] = Field(
        default=None, description="Known language constraints; null means no evaluator-specific restriction is declared. Host execution support is separate.")
    requires_sandbox: bool


class TemplateDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifier: str
    name: str
    description: str
    requires_sandbox: bool
    evaluators: List[EvaluatorDescription]


class TemplateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    templates: List[TemplateDescription]
    capabilities: Dict[Capability, str] = Field(
        default_factory=lambda: dict(CAPABILITY_DESCRIPTIONS),
        description="Why each capability may be unavailable on a host.")


def parameters_schema(function: TestFunction) -> Dict[str, Any]:
    """JSON Schema of the exact contract used by compile_definition."""
    return {**function.config_schema.model_json_schema(), "additionalProperties": False}


def _sample(schema: Mapping[str, Any], defs: Mapping[str, Any]) -> Any:
    if "default" in schema:
        return schema["default"]
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "$ref" in schema:
        return _sample(defs[schema["$ref"].rsplit("/", 1)[-1]], defs)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [option for option in schema[key] if option.get("type") != "null"]
            return _sample(options[0], defs)
    kind = schema.get("type")
    if kind == "string":
        return "example" if schema.get("minLength", 0) <= 7 else "x" * schema["minLength"]
    if kind in ("integer", "number"):
        return max(1, schema.get("minimum", 1))
    if kind == "boolean":
        return True
    if kind == "array":
        return [_sample(schema.get("items", {"type": "string"}), defs) for _ in range(schema.get("minItems", 0))]
    if kind == "object":
        return {name: _sample(schema["properties"][name], defs) for name in schema.get("required", [])}
    return "example"


def sample_parameters(function: TestFunction) -> Dict[str, Any]:
    """Validate examples against the executable contract before publishing them.

    Simple required fields can be synthesized. Evaluators with constraints that
    need domain knowledge must provide example_parameters on the implementation.
    """
    explicit = getattr(function, "example_parameters", None)
    schema = function.config_schema.model_json_schema()
    candidate = dict(explicit) if explicit is not None else _sample(schema, schema.get("$defs", {}))
    try:
        return function.config_schema.model_validate(candidate, strict=True, extra="forbid").model_dump(mode="json")
    except ValueError as exc:
        raise ValueError(f"Evaluator '{function.name}' must supply valid example_parameters") from exc


def required_capabilities(template: Template, function: TestFunction) -> List[str]:
    capabilities = set(getattr(function, "required_capabilities", ()))
    if template.requires_sandbox:
        capabilities.add("sandbox_execution")
    return sorted(capabilities)


def describe_template(identifier: str, template: Template) -> TemplateDescription:
    if not isinstance(template, Template):
        raise TypeError("Injected templates must be trusted Template instances")
    template.validate_contract()
    return TemplateDescription(
        identifier=identifier,
        name=template.template_name,
        description=template.template_description,
        requires_sandbox=template.requires_sandbox,
        evaluators=[EvaluatorDescription(
            identifier=name,
            description=function.description,
            parameters_schema=parameters_schema(function),
            sample_parameters=sample_parameters(function),
            required_capabilities=required_capabilities(template, function),
            supported_languages=getattr(function, "supported_languages", None),
            requires_sandbox=template.requires_sandbox,
        ) for name, function in template.get_tests().items()])


def describe_templates(templates: Optional[Mapping[str, Template]] = None) -> TemplateCatalog:
    """Describe built-in templates plus trusted injected ``Template`` instances.

    Injected identifiers replace built-ins exactly as in ``compile_definition``.
    """
    from autograder.services.template_library_service import TemplateLibraryService
    library = TemplateLibraryService.get_instance()
    resolved: Dict[str, Template] = {name: library.start_template(name) for name in library.list_available_templates()}
    resolved.update(templates or {})
    return TemplateCatalog(templates=[describe_template(name, template) for name, template in resolved.items()])
