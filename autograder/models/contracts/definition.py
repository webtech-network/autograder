"""Versioned, provider-free grading definition and pure compilation boundary."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Literal, Mapping
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator, model_validator
from autograder.models.abstract.template import Template
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.contracts.parameters import LanguageId
from sandbox_manager.models.sandbox_models import Language


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def relative_path(value: str) -> str:
    parts = PurePosixPath(value).parts
    if not value or value.startswith('/') or '\\' in value or '\x00' in value or '..' in parts or value != str(PurePosixPath(value)) or value == '.':
        raise ValueError("must be a normalized relative path without traversal")
    return value


class SetupCommand(StrictModel):
    name: str = Field(min_length=1)
    command: str = Field(min_length=1)


class LanguagePreparation(StrictModel):
    required_files: list[str] = Field(default_factory=list)
    setup_commands: list[SetupCommand] = Field(default_factory=list)

    @field_validator('required_files')
    @classmethod
    def validate_files(cls, values):
        for value in values:
            relative_path(value)
        if len(set(values)) != len(values):
            raise ValueError("required files must be unique")
        return values


class Fixture(StrictModel):
    reference: str = Field(min_length=1)

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value):
        return relative_path(value)

    path: str
    read_only: bool = True

    @field_validator('path')
    @classmethod
    def validate_path(cls, value):
        return relative_path(value)


class Preparation(StrictModel):
    languages: dict[LanguageId, LanguagePreparation] = Field(default_factory=dict)
    fixtures: list[Fixture] = Field(default_factory=list)

    @model_validator(mode='after')
    def distinct_targets(self):
        paths = [fixture.path for fixture in self.fixtures]
        if len(set(paths)) != len(paths):
            raise ValueError("fixture paths must be unique")
        return self

    def runtime_setup(self) -> dict:
        """Translate fixture-root paths for the current sandbox host, not a wire alias."""
        setup = {key: value.model_dump(mode='json') for key, value in self.languages.items()}
        if self.fixtures:
            setup['assets'] = [{'source': fixture.reference, 'target': '/tmp/app/' + fixture.path,
                                'read_only': fixture.read_only} for fixture in self.fixtures]
        return setup


class LearningResource(StrictModel):
    url: str = Field(min_length=1)
    description: str
    linked_tests: list[str] = Field(default_factory=list)


class GeneralPreferences(StrictModel):
    report_title: str | None = None
    show_score: bool = True
    show_passed_tests: bool = False
    add_report_summary: bool = True
    online_content: list[LearningResource] = Field(default_factory=list)


class DefaultPreferences(StrictModel):
    category_headers: dict[Literal['base', 'bonus', 'penalty'], str] = Field(default_factory=dict)


class FeedbackPreferences(StrictModel):
    general: GeneralPreferences = Field(default_factory=GeneralPreferences)
    default: DefaultPreferences = Field(default_factory=DefaultPreferences)


class Feedback(StrictModel):
    enabled: bool = False
    mode: Literal['default'] = 'default'
    preferences: FeedbackPreferences = Field(default_factory=FeedbackPreferences)


class GradingDefinition(StrictModel):
    schema_version: Literal['1.0']
    templates: list[str] = Field(min_length=1)
    languages: list[LanguageId] = Field(min_length=1)
    criteria: CriteriaConfig
    preparation: Preparation = Field(default_factory=Preparation)
    feedback: Feedback = Field(default_factory=Feedback)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_structure(self):
        for field in ('templates', 'languages'):
            values = getattr(self, field)
            if len(set(values)) != len(values) or any(not value.strip() or value != value.strip() for value in values):
                raise ValueError(f"{field} must contain distinct nonempty canonical identifiers")
        if self.criteria.base.weight != 100:
            raise ValueError("base weight must equal 100; bonus and penalty weights are caps")
        if not set(self.preparation.languages).issubset(self.languages):
            raise ValueError("preparation languages must be allowed by the definition")
        return self


class DefinitionValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        self._errors = errors
        super().__init__('Invalid grading definition')

    def errors(self):
        return self._errors


def _error(code, path, message):
    return {'code': code, 'path': list(path), 'message': message}


def _pydantic_errors(exc, prefix=()):
    return [_error('INVALID_DEFINITION', (*prefix, *item['loc']), item['msg'])
            for item in exc.errors(include_url=False, include_input=False)]


def walk_tests(criteria):
    """Yield test models and JSON paths in deterministic definition order."""
    def walk(group, path):
        for index, test in enumerate(group.tests or []):
            yield test, (*path, 'tests', index)
        for index, subject in enumerate(group.subjects or []):
            yield from walk(subject, (*path, 'subjects', index))
    for name in ('base', 'bonus', 'penalty'):
        category = getattr(criteria, name)
        if category is not None:
            yield from walk(category, ('criteria', name))


@dataclass(frozen=True)
class CompiledDefinition:
    definition: GradingDefinition
    definition_hash: str
    criteria_tree: CriteriaTree
    templates: list[Template]


def compile_definition(value: GradingDefinition | dict | CompiledDefinition, *, templates: Mapping[str, Template] | None = None) -> CompiledDefinition:
    """Validate and normalize every criterion before storing/enqueuing work."""
    if isinstance(value, CompiledDefinition):
        # Never bypass validation of a mutable caller-owned Pydantic model.
        if templates is None:
            templates = dict(zip(value.definition.templates, value.templates))
        value = value.definition
    if isinstance(value, GradingDefinition):
        value = value.model_dump(mode='json')
    try:
        definition = GradingDefinition.model_validate(value)
    except ValidationError as exc:
        raise DefinitionValidationError(_pydantic_errors(exc)) from exc
    from autograder.services.template_library_service import TemplateLibraryService
    library = TemplateLibraryService.get_instance()
    selected, registry, errors = [], {}, []
    for index, identifier in enumerate(definition.templates):
        try:
            template = templates[identifier] if templates is not None and identifier in templates else library.load_builtin_template(identifier)
        except KeyError:
            errors.append(_error('UNKNOWN_TEMPLATE', ('templates', index), 'Unknown template identifier'))
            continue
        try:
            if not isinstance(template, Template):
                raise TypeError('Injected templates must be trusted Template instances')
            template.validate_contract()
        except (TypeError, ValueError) as exc:
            errors.append(_error('INVALID_TEMPLATE', ('templates', index), str(exc)))
            continue
        selected.append(template)
        for name, function in template.get_tests().items():
            if name in registry:
                errors.append(_error('AMBIGUOUS_EVALUATOR', ('templates', index), f'Duplicate evaluator identifier: {name}'))
            registry[name] = function
    seen = set()
    for test, path in walk_tests(definition.criteria):
        if test.id in seen:
            errors.append(_error('DUPLICATE_CRITERION_ID', (*path, 'id'), 'Criterion IDs must be unique throughout the definition'))
        seen.add(test.id)
        if test.file:
            try:
                relative_path(test.file)
            except ValueError as exc:
                errors.append(_error('INVALID_PATH', (*path, 'file'), str(exc)))
        function = registry.get(test.type)
        if function is None:
            errors.append(_error('UNKNOWN_EVALUATOR', (*path, 'type'), 'Evaluator is not registered in selected templates'))
            continue
        from autograder.models.contracts.parameter_contract import RUNTIME_PARAMETERS
        reserved = set(test.parameters) & RUNTIME_PARAMETERS
        if reserved:
            errors.append(_error("RESERVED_PARAMETER", (*path, "parameters", sorted(reserved)[0]), "Runtime context cannot be supplied by a definition"))
            continue
        try:
            schema = function.config_schema
            if schema is None:
                raise ValueError('Evaluator must expose a parameter contract')
            normalized = schema.model_validate(test.parameters, strict=True, extra="forbid")
            test.parameters = normalized.model_dump(mode='json')
        except ValidationError as exc:
            errors.extend(_pydantic_errors(exc, (*path, 'parameters')))
            continue
        except (ValueError, TypeError) as exc:
            errors.append(_error('INVALID_PARAMETER_CONTRACT', (*path, 'parameters'), str(exc)))
            continue
        command = test.parameters.get('program_command')
        if isinstance(command, dict) and not set(definition.languages).issubset(command):
            errors.append(_error('MISSING_LANGUAGE_COMMAND', (*path, 'parameters', 'program_command'), 'Command map must cover every allowed language'))
        if 'forbidden_keywords' in test.parameters:
            from autograder.template_library.static_analysis import ForbiddenKeywordTest
            for keyword_index, keyword in enumerate(test.parameters['forbidden_keywords']):
                if any(keyword not in ForbiddenKeywordTest.PREDEFINED_RULES.get(Language(language), {}) for language in definition.languages):
                    errors.append(_error('UNSUPPORTED_KEYWORD', (*path, 'parameters', 'forbidden_keywords', keyword_index), 'Keyword must be supported for every allowed language'))
        for rule_index, rule in enumerate(test.parameters.get('custom_ast_grep_rules', [])):
            if not isinstance(rule, dict) or not rule or not set(rule).issubset({'kind','pattern','regex','all','any','not','has','inside','precedes','follows'}):
                errors.append(_error('INVALID_AST_RULE', (*path,'parameters','custom_ast_grep_rules',rule_index), 'Expected an ast-grep rule object'))
                continue
            from ast_grep_py import SgRoot
            grammar_names = {'node': 'javascript', 'python': 'python', 'java': 'java', 'cpp': 'cpp', 'c': 'c'}
            try:
                for language in definition.languages:
                    SgRoot('', grammar_names[language]).root().find_all(**rule)
            except Exception:
                errors.append(_error('INVALID_AST_RULE', (*path,'parameters','custom_ast_grep_rules',rule_index), 'Rule must compile for every allowed language'))
    for resource_index, resource in enumerate(definition.feedback.preferences.general.online_content):
        if not set(resource.linked_tests).issubset(seen):
            errors.append(_error('UNKNOWN_CRITERION_REFERENCE', ('feedback','preferences','general','online_content',resource_index,'linked_tests'), 'Learning resources must reference criterion IDs'))
    if errors:
        raise DefinitionValidationError(errors)
    from autograder.services.criteria_tree_service import CriteriaTreeService
    tree = CriteriaTreeService().build_tree(definition.criteria, selected)
    payload = json.dumps(definition.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    return CompiledDefinition(definition, hashlib.sha256(payload).hexdigest(), tree, selected)


def select_language(definition: GradingDefinition | CompiledDefinition, supplied=None) -> Language:
    if isinstance(definition, CompiledDefinition):
        definition = definition.definition
    value = supplied.value if isinstance(supplied, Language) else supplied
    if value is None and len(definition.languages) == 1:
        value = definition.languages[0]
    if value is None:
        raise DefinitionValidationError([_error('LANGUAGE_REQUIRED', ('language',), 'Select one of the allowed languages')])
    if value not in definition.languages:
        raise DefinitionValidationError([_error('LANGUAGE_NOT_ALLOWED', ('language',), 'Language is not allowed by this definition')])
    return Language(value)


def grading_definition_json_schema() -> dict:
    """Structural schema plus evaluator-conditional parameter contracts."""
    schema = GradingDefinition.model_json_schema()
    from autograder.services.template_library_service import TemplateLibraryService
    conditions = []
    definitions = schema['$defs']
    for identifier in TemplateLibraryService.get_instance().list_available_templates():
        template = TemplateLibraryService.get_instance().load_builtin_template(identifier)
        for name, function in template.get_tests().items():
            parameters = function.config_schema.model_json_schema()
            parameters['additionalProperties'] = False
            for key, item in parameters.pop('$defs', {}).items():
                if key in definitions and definitions[key] != item:
                    raise ValueError(f'Conflicting parameter schema definition: {key}')
                definitions[key] = item
            conditions.append({'if': {'properties': {'type': {'const': name}}, 'required':['type']},
                               'then': {'properties': {'parameters': parameters}}})
    schema['$defs']['TestConfig']['allOf'] = conditions
    schema['$defs']['TestConfig']['properties']['type']['enum'] = sorted({condition['if']['properties']['type']['const'] for condition in conditions})
    schema['$id'] = 'https://webtech.network/autograder/contracts/grading-definition/1.0'
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    return schema
