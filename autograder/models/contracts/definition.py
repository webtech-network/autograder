"""Versioned, provider-free grading definition and pure compilation boundary."""
import difflib
import hashlib
import json
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator, model_validator
from pydantic.json_schema import GenerateJsonSchema
from autograder.models.abstract.template import Template
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.frozen import freeze, thaw
from autograder.models.language import Language, LanguageId
from autograder.models.process import SHELL_OPERATOR_MESSAGE, shell_operator, split_command


class ContractJsonSchema(GenerateJsonSchema):
    """Publish every default compilation applies, including ``default_factory`` ones.

    Pydantic omits factory defaults (``[]``, ``{}``, nested preference objects)
    from JSON Schema; discovery, the published schema and the generated
    reference must state them.
    """

    def get_default_value(self, schema):
        factory = schema.get('default_factory')
        if factory is not None and not schema.get('default_factory_takes_data'):
            return factory()
        return super().get_default_value(schema)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def relative_path(value: str) -> str:
    parts = PurePosixPath(value).parts
    if not value or value.startswith('/') or '\\' in value or '\x00' in value or '..' in parts or value != str(PurePosixPath(value)) or value == '.':
        raise ValueError("must be a normalized relative path without traversal")
    return value


class SetupCommand(StrictModel):
    """One preparation step, run once before assessment in the selected language's sandbox."""
    name: str = Field(min_length=1, description="Label of the step, shown when it fails.")
    command: str = Field(min_length=1, description=(
        "Executable and arguments, split with POSIX quoting and run without a shell. "
        "Standalone shell operators (&&, |, ;, >, ...) are rejected: use one setup command per step, "
        "and an explicit `sh -c '...'` command only for a real pipeline."))
    # Omitted from the snapshot while false, so definitions written before the
    # field existed keep their hash.
    private_output: bool = Field(default=False, exclude_if=lambda value: value is False, description=(
        "Keep this step's output out of the student-facing failure explanation, for example when it "
        "compiles a hidden test harness. By default a failing step's output excerpt is shown."))

    @field_validator('command')
    @classmethod
    def validate_command(cls, value):
        split_command(value)  # malformed quoting is rejected, never run through a shell
        return value


class LanguagePreparation(StrictModel):
    """Preparation for one allowed language."""
    required_files: list[str] = Field(default_factory=list, description=(
        "Unique relative submission paths that must exist; a missing one fails with REQUIRED_FILE_MISSING "
        "before any sandbox is acquired."))
    setup_commands: list[SetupCommand] = Field(default_factory=list, description=(
        "Steps run in order after fixtures are staged, for example compilation. A failing step stops "
        "grading with PREPARATION_FAILED."))

    @field_validator('required_files')
    @classmethod
    def validate_files(cls, values):
        for value in values:
            relative_path(value)
        if len(set(values)) != len(values):
            raise ValueError("required files must be unique")
        return values


class Fixture(StrictModel):
    """A host-provided file staged into the sandbox before setup commands."""
    reference: str = Field(min_length=1, description=(
        "Logical relative reference resolved by the host's fixture provider (an object key on the shipped hosts)."))

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value):
        return relative_path(value)

    path: str = Field(description="Unique relative destination under the fixture root (/tmp/app on the shipped hosts).")
    read_only: bool = Field(default=True, description="Whether the staged file is read-only to the submission.")

    @field_validator('path')
    @classmethod
    def validate_path(cls, value):
        return relative_path(value)


class Preparation(StrictModel):
    """What must exist and run before any criterion is assessed."""
    languages: dict[LanguageId, LanguagePreparation] = Field(default_factory=dict, description=(
        "Preparation keyed by allowed language; only the submission's language is used."))
    fixtures: list[Fixture] = Field(default_factory=list, description="Files staged for every language.")

    @model_validator(mode='after')
    def distinct_targets(self):
        paths = [fixture.path for fixture in self.fixtures]
        if len(set(paths)) != len(paths):
            raise ValueError("fixture paths must be unique")
        return self



class LearningResource(StrictModel):
    """A link listed in the feedback report."""
    url: str = Field(min_length=1, description="Address of the resource.")
    description: str = Field(description="Link text shown in the report.")
    linked_tests: list[str] = Field(default_factory=list, description=(
        "Criterion IDs; the resource is shown only when one of them scored below 100. Empty shows it always."))


class GeneralPreferences(StrictModel):
    """Report options shared by every feedback mode."""
    report_title: str | None = Field(default=None, description=(
        "Report heading; null uses the localized default title."))
    show_score: bool = Field(default=True, description="Whether the report shows the final score.")
    show_passed_tests: bool = Field(default=False, description=(
        "Whether criteria that scored 100 are listed; by default only criteria below 100 are."))
    add_report_summary: bool = Field(default=True, description="Whether the report starts with a score summary.")
    online_content: list[LearningResource] = Field(default_factory=list, description=(
        "Learning resources listed at the end of the report."))


class DefaultPreferences(StrictModel):
    """Options of the default Markdown report."""
    category_headers: dict[Literal['base', 'bonus', 'penalty'], str] = Field(default_factory=dict, description=(
        "Section heading per category; a missing category uses its localized default heading."))


class FeedbackPreferences(StrictModel):
    """How the feedback report is written."""
    general: GeneralPreferences = Field(default_factory=GeneralPreferences, description="Options for every mode.")
    default: DefaultPreferences = Field(default_factory=DefaultPreferences, description=(
        "Options of the default mode."))


class Feedback(StrictModel):
    """Whether and how a feedback report is written for a completed grade."""
    enabled: bool = Field(default=False, description=(
        "Whether a feedback report is rendered; disabled feedback does no work."))
    mode: Literal['default'] = Field(default='default', description="Report format; only the Markdown default exists.")
    preferences: FeedbackPreferences = Field(default_factory=FeedbackPreferences, description="Report options.")


#: The one definition format this engine reads.
SCHEMA_VERSION = '2.0'

#: How to bring a definition in an earlier format to this one; nothing converts at runtime.
CONVERT_COMMAND = 'python -m autograder.services.definition_migration old.json definition.json'


class GradingDefinition(StrictModel):
    """One assignment's complete grading definition (version 2.0)."""
    schema_version: Literal['2.0'] = Field(description="Definition format version.")
    languages: list[LanguageId] = Field(min_length=1, description=(
        "Distinct languages a submission may use; with several, each submission names its language."))
    criteria: CriteriaConfig = Field(description="The weighted criteria tree.")
    preparation: Preparation = Field(default_factory=Preparation, description=(
        "Required files, fixtures and setup commands."))
    feedback: Feedback = Field(default_factory=Feedback, description="Feedback report policy.")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description=(
        "Free-form JSON stored with the definition; never interpreted by grading."))

    @model_validator(mode='after')
    def validate_structure(self):
        for index, value in enumerate(self.languages):
            if value in self.languages[:index]:
                raise FieldError("languages must be distinct", 'languages', index)
        for language in self.preparation.languages:
            if language not in self.languages:
                raise FieldError(f"preparation for `{language}` is never used: add it to `languages` "
                                 f"({', '.join(self.languages)}) or remove it", 'preparation', 'languages', language)
        return self


class FieldError(ValueError):
    """A rule a model checks across fields, broken by one of them.

    ``path`` is relative to the model that raises it; compilation and the HTTP
    host append it to pydantic's location, so the error names that field instead
    of the model (``criteria.base.weight`` rather than the whole definition).
    """

    def __init__(self, message: str, *path: str | int):
        super().__init__(message)
        self.path = path


#: Fields of format 1.0 that 2.0 rejects, keyed by the end of their path, with what replaced them.
REMOVED_FIELDS = {
    ('templates',): "A definition lists no `templates`: `type` alone names the evaluator",
    ('base', 'weight'): ("The base category has no weight: it is the 0-100 score "
                         "(bonus and penalty categories set `max_points`)"),
    ('bonus', 'weight'): "A bonus category caps the points it adds with `max_points`",
    ('penalty', 'weight'): "A penalty category caps the points it subtracts with `max_points`",
    ('subject_name',): "A subject is labelled with `name`, like a criterion",
}


def validation_error_detail(item: dict) -> tuple[tuple, str]:
    """The JSON path and plain message of one pydantic error item (``ValidationError.errors()``).

    A :class:`FieldError` extends the path to its field; a validator's own
    message is returned without pydantic's "Value error, " prefix; a field
    removed in format 2.0 names its replacement.
    """
    if item['type'] == 'extra_forbidden':
        for suffix, message in REMOVED_FIELDS.items():
            if tuple(item['loc'][-len(suffix):]) == suffix:
                return tuple(item['loc']), message
    error = (item.get('ctx') or {}).get('error')
    if isinstance(error, FieldError):
        return (*item['loc'], *error.path), str(error)
    if item['type'] in ('value_error', 'assertion_error') and isinstance(error, Exception):
        return tuple(item['loc']), str(error)
    return tuple(item['loc']), item['msg']


def suggestion(value: str, candidates, describe=lambda match: f"`{match}`") -> str:
    """``"; did you mean `x`?"`` for the closest candidate, or nothing when none is close."""
    matches = difflib.get_close_matches(value, list(candidates), n=1)
    return f"; did you mean {describe(matches[0])}?" if matches else ""


class DefinitionValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        self._errors = errors
        super().__init__('Invalid grading definition')

    def errors(self):
        return self._errors


def _error(code, path, message):
    return {'code': code, 'path': list(path), 'message': message}


def _pydantic_errors(exc, prefix=()):
    errors = [_error('INVALID_DEFINITION', (*prefix, *path), message)
              for path, message in map(validation_error_detail, exc.errors(include_url=False, include_input=False))]
    # A field removed in 2.0 explains the missing field that replaced it, so it comes first.
    return sorted(errors, key=lambda error: error['message'] not in REMOVED_FIELDS.values())


def _parameter_errors(exc, prefix, evaluator, schema):
    """Parameter errors; an unknown parameter names the evaluator's closest one or lists them."""
    accepted = list(schema.model_fields)
    errors = _pydantic_errors(exc, prefix)
    for item, error in zip(exc.errors(include_url=False, include_input=False), errors):
        if item['type'] == 'extra_forbidden' and len(item['loc']) == 1:
            name = str(item['loc'][0])
            error['message'] = (f"`{evaluator}` has no parameter `{name}`"
                                + (suggestion(name, accepted) or f"; it accepts: {', '.join(accepted) or 'none'}"))
    return errors


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


class CompiledDefinition:
    """A validated, deeply immutable grading plan.

    Only ``compile_definition`` and ``compile_snapshot`` create one, so holding
    a ``CompiledDefinition`` means its canonical snapshot, hash, criteria tree and
    trusted templates were produced together. Reading ``definition`` returns a
    fresh model copy; changing that copy cannot alter this plan.
    """
    __slots__ = ('_snapshot', '_definition_hash', '_criteria_tree', '_templates', '_max_outcome_bytes')

    def __init__(self, *args, **kwargs):
        raise TypeError('CompiledDefinition is created only by compile_definition or compile_snapshot')

    @classmethod
    def _create(cls, snapshot: dict, definition_hash: str, criteria_tree: CriteriaTree,
                templates: Mapping[str, Template], max_outcome_bytes: int) -> 'CompiledDefinition':
        compiled = object.__new__(cls)
        object.__setattr__(compiled, '_max_outcome_bytes', max_outcome_bytes)
        object.__setattr__(compiled, '_snapshot', freeze(snapshot))
        object.__setattr__(compiled, '_definition_hash', definition_hash)
        object.__setattr__(compiled, '_criteria_tree', criteria_tree)
        object.__setattr__(compiled, '_templates', MappingProxyType(dict(templates)))
        return compiled

    def __setattr__(self, name, value):
        raise AttributeError('CompiledDefinition is immutable')

    def __delattr__(self, name):
        raise AttributeError('CompiledDefinition is immutable')

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __repr__(self):
        return f'CompiledDefinition(definition_hash={self._definition_hash!r})'

    @property
    def definition(self) -> GradingDefinition:
        """A fresh copy of the canonical definition snapshot."""
        return GradingDefinition.model_validate(thaw(self._snapshot))

    @property
    def definition_hash(self) -> str:
        return self._definition_hash

    @property
    def criteria_tree(self) -> CriteriaTree:
        return self._criteria_tree

    @property
    def max_outcome_bytes(self) -> int:
        """Worst-case serialized size of any outcome of this definition (OUTCOMES.md)."""
        return self._max_outcome_bytes

    @property
    def templates(self) -> Mapping[str, Template]:
        """The trusted templates injected at compilation, keyed by identifier.

        Built-in templates are always available; criteria resolve evaluators by
        ``type`` across both, and an identifier offered twice is ambiguous.
        """
        return self._templates


def compile_definition(value: GradingDefinition | dict | CompiledDefinition, *,
                       templates: Mapping[str, Template] | None = None) -> CompiledDefinition:
    """Validate raw authoring input and normalize every criterion exactly once.

    The normalized values form the canonical snapshot, its hash and the executed
    criteria tree. A ``CompiledDefinition`` is returned unchanged; supplying
    ``templates`` with one revalidates its canonical snapshot (see
    ``compile_snapshot``) against those templates without normalizing again.
    """
    if isinstance(value, CompiledDefinition):
        if templates is None:
            return value
        return _compile(thaw(value._snapshot), {**value.templates, **templates}, canonical=True)  # pylint: disable=protected-access
    return _compile(value, templates, canonical=False)


def compile_snapshot(snapshot: GradingDefinition | dict, *,
                     templates: Mapping[str, Template] | None = None) -> CompiledDefinition:
    """Validate a stored canonical snapshot without applying raw normalization.

    Use this at trust boundaries that receive an already-compiled definition
    (stored configurations, bound execution snapshots, external attestations).
    Structure, registry, evaluator contracts and cross-field rules are still
    checked, but parameter values are kept verbatim, so a snapshot's meaning
    and hash cannot change when it is loaded again. Every contract field must be
    explicit, as in a compiled snapshot.
    """
    if isinstance(snapshot, CompiledDefinition):
        raise TypeError('compile_snapshot expects a serialized snapshot; reuse the CompiledDefinition directly')
    return _compile(snapshot, templates, canonical=True)


def _compile(value, templates: Mapping[str, Template] | None, *, canonical: bool) -> CompiledDefinition:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    if isinstance(value, GradingDefinition):
        value = value.model_dump(mode='json')
    if isinstance(value, dict) and value.get('schema_version') == '1.0':
        raise DefinitionValidationError([_error('UNSUPPORTED_SCHEMA_VERSION', ('schema_version',), (
            f"This engine reads definition format {SCHEMA_VERSION}; convert this definition offline with "
            f"`{CONVERT_COMMAND}`"))])
    try:
        definition = GradingDefinition.model_validate(value)
    except ValidationError as exc:
        raise DefinitionValidationError(_pydantic_errors(exc)) from exc
    from autograder.template_library import BUILTIN_TEMPLATES
    available = {**BUILTIN_TEMPLATES, **(templates or {})}
    errors = []
    for identifier, template in (templates or {}).items():
        try:
            if not isinstance(template, Template):
                raise TypeError('Injected templates must be trusted Template instances')
            template.validate_contract()
        except (TypeError, ValueError) as exc:
            errors.append(_error('INVALID_TEMPLATE', (), f"Template `{identifier}`: {exc}"))
            available.pop(identifier)
    injected = {identifier: available[identifier] for identifier in templates or {} if identifier in available}
    providers = {}
    for identifier, template in available.items():
        for name, function in template.get_tests().items():
            providers.setdefault(name, []).append((identifier, function))
    registry = {name: found[0][1] for name, found in providers.items() if len(found) == 1}
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
        if len(providers.get(test.type, ())) > 1:
            errors.append(_error('AMBIGUOUS_EVALUATOR', (*path, 'type'), (
                f"Evaluator `{test.type}` is provided by several templates "
                f"({', '.join(sorted(identifier for identifier, _ in providers[test.type]))}); "
                "give the injected evaluator a distinct name")))
            continue
        if test.type not in registry:
            errors.append(_error('UNKNOWN_EVALUATOR', (*path, 'type'),
                                 f"Unknown evaluator `{test.type}`" + suggestion(test.type, registry)))
            continue
        function = registry[test.type]
        from autograder.models.contracts.parameter_contract import RUNTIME_PARAMETERS
        reserved = set(test.parameters) & RUNTIME_PARAMETERS
        if reserved:
            errors.append(_error("RESERVED_PARAMETER", (*path, "parameters", sorted(reserved)[0]), "Runtime context cannot be supplied by a definition"))
            continue
        try:
            normalized = function.config_schema.model_validate(test.parameters, strict=True, extra="forbid").model_dump(mode='json')
        except ValidationError as exc:
            errors.extend(_parameter_errors(exc, (*path, 'parameters'), test.type, function.config_schema))
            continue
        except (ValueError, TypeError) as exc:
            errors.append(_error('INVALID_PARAMETER_CONTRACT', (*path, 'parameters'), str(exc)))
            continue
        if canonical:
            # Canonical values are checked, never transformed a second time.
            if set(normalized) != set(test.parameters):
                errors.append(_error('NON_CANONICAL_PARAMETERS', (*path, 'parameters'),
                                     'Snapshot parameters must list every normalized parameter'))
                continue
        else:
            test.parameters = normalized
        # Evaluator-owned semantics (command coverage, AST rules, ...) on an isolated copy.
        try:
            issues = list(function.validate_parameters(thaw(test.parameters), languages=tuple(definition.languages)))
        except (TypeError, ValueError) as exc:
            errors.append(_error('INVALID_PARAMETER_CONTRACT', (*path, 'parameters'), str(exc)))
            continue
        errors.extend(_error(issue.code, (*path, 'parameters', *issue.path), issue.message) for issue in issues)
    for language, preparation in definition.preparation.languages.items():
        for index, setup in enumerate(preparation.setup_commands):
            operator = shell_operator(setup.command)
            if operator is not None:
                errors.append(_error('SHELL_OPERATOR', ('preparation', 'languages', language, 'setup_commands', index, 'command'),
                                     SHELL_OPERATOR_MESSAGE.format(operator=operator)))
    for resource_index, resource in enumerate(definition.feedback.preferences.general.online_content):
        if not set(resource.linked_tests).issubset(seen):
            errors.append(_error('UNKNOWN_CRITERION_REFERENCE', ('feedback','preferences','general','online_content',resource_index,'linked_tests'), 'Learning resources must reference criterion IDs'))
    if errors:
        raise DefinitionValidationError(errors)
    from autograder.services.criteria_tree_service import build_criteria_tree
    from autograder.models.contracts.outcome import wire_bytes
    from autograder.models.contracts.verification import MAX_ATTESTATION_BYTES
    from autograder.services.grading import max_outcome_bytes
    snapshot = definition.model_dump(mode='json')
    tree = build_criteria_tree(definition.criteria, registry)
    # Every outcome travels with its definition snapshot; both must fit in one
    # attestation whatever the submission does.
    outcome_bytes = max_outcome_bytes(tree)
    if wire_bytes(snapshot) + outcome_bytes > MAX_ATTESTATION_BYTES:
        raise DefinitionValidationError([_error(
            'DEFINITION_TOO_LARGE', (), f'The definition and its worst-case outcome exceed {MAX_ATTESTATION_BYTES} '
            'bytes; reduce the number of criteria or the size of their parameters')])
    return CompiledDefinition._create(snapshot, definition_hash(definition), tree, injected,  # pylint: disable=protected-access
                                      outcome_bytes)


def definition_hash(definition: GradingDefinition) -> str:
    """SHA-256 over sorted, compact UTF-8 JSON of an already normalized definition."""
    return snapshot_hash(definition.model_dump(mode='json'))


def snapshot_hash(snapshot: Mapping) -> str:
    """The definition hash of a stored canonical snapshot, in whatever format version it was written.

    It reads no field, so a snapshot bound before a format change still
    verifies against the provenance recorded with its outcome.
    """
    payload = json.dumps(thaw(snapshot), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def select_language(definition: GradingDefinition | CompiledDefinition, supplied=None) -> Language:
    if isinstance(definition, CompiledDefinition):
        definition = definition.definition
    value = supplied.value if isinstance(supplied, Language) else supplied
    if value is None and len(definition.languages) == 1:
        value = definition.languages[0]
    allowed = ', '.join(definition.languages)
    if value is None:
        raise DefinitionValidationError([_error('LANGUAGE_REQUIRED', ('language',),
                                                f'Select one of the allowed languages: {allowed}')])
    if value not in definition.languages:
        raise DefinitionValidationError([_error('LANGUAGE_NOT_ALLOWED', ('language',),
                                                f'Language is not allowed by this definition; allowed: {allowed}')])
    return Language(value)


def grading_definition_json_schema() -> dict:
    """Structural schema plus evaluator-conditional parameter contracts."""
    schema = GradingDefinition.model_json_schema(schema_generator=ContractJsonSchema)
    from autograder.template_library import BUILTIN_TEMPLATES
    conditions = []
    definitions = schema['$defs']
    for template in BUILTIN_TEMPLATES.values():
        for name, function in template.get_tests().items():
            parameters = function.config_schema.model_json_schema(schema_generator=ContractJsonSchema)
            parameters['additionalProperties'] = False
            for key, item in parameters.pop('$defs', {}).items():
                if key in definitions and definitions[key] != item:
                    raise ValueError(f'Conflicting parameter schema definition: {key}')
                definitions[key] = item
            conditions.append({'if': {'properties': {'type': {'const': name}}, 'required':['type']},
                               'then': {'properties': {'parameters': parameters}}})
    schema['$defs']['TestConfig']['allOf'] = conditions
    schema['$defs']['TestConfig']['properties']['type']['enum'] = sorted({condition['if']['properties']['type']['const'] for condition in conditions})
    schema['$id'] = 'https://webtech.network/autograder/contracts/grading-definition/2.0'
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    return schema
