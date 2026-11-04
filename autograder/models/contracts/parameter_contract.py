"""The evaluator invocation contract and its signature-derived parameter model.

Every evaluator has one entry point (``execute``, or ``build_prompt`` for AI
evaluators) declared as::

    def execute(self, evaluation: EvaluationInput, *, <configuration>) -> TestResult

The single positional argument is the typed runtime input. Keyword-only
parameters are exactly the evaluator's normalized configuration: the fields of
its parameter contract. Annotations and defaults are used verbatim; constraints
such as ``min_length`` or ``ge`` exist only when the evaluator declares them
with ``Annotated[..., Field(...)]`` or an explicit ``config_schema``.
"""
import inspect
from typing import get_type_hints
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, create_model

#: Runtime names that can never be configuration: they would be indistinguishable
#: from historical runtime context in authored definitions.
RUNTIME_PARAMETERS = frozenset({
    "files", "sandbox", "session", "evaluation", "submission_files", "submission_language",
    "structural_analysis", "context_files", "locale", "evaluation_scope", "file_metadata",
    "pre_computed_results", "precomputed_results", "criterion_id",
})

_DERIVED: "WeakKeyDictionary[type, type[BaseModel]]" = WeakKeyDictionary()


def _configuration(method) -> list[inspect.Parameter]:
    return [parameter for parameter in inspect.signature(method).parameters.values()
            if parameter.kind is inspect.Parameter.KEYWORD_ONLY]


def signature_contract(function) -> type[BaseModel]:
    """Strict model of an entry point's annotated keyword-only parameters."""
    cls = type(function)
    if cls not in _DERIVED:
        method = function.entrypoint
        hints = get_type_hints(getattr(cls, method.__name__), include_extras=True)
        fields = {}
        for parameter in _configuration(method):
            if parameter.name not in hints:
                raise TypeError(f"Evaluator '{cls.__name__}' must annotate configuration parameter '{parameter.name}'")
            annotation = hints[parameter.name]
            fields[parameter.name] = annotation if parameter.default is inspect.Parameter.empty else (annotation, parameter.default)
        _DERIVED[cls] = create_model(cls.__name__ + "Parameters", __config__=ConfigDict(
            extra="forbid", strict=True, allow_inf_nan=False, validate_default=True), **fields)
    return _DERIVED[cls]


def check_invocation(function) -> None:
    """Reject an entry point that does not match the supported call shape."""
    method = function.entrypoint
    label = f"Evaluator '{type(function).__name__}'"
    shape = f"{method.__name__}(self, evaluation, *, <parameters>)"
    parameters = list(inspect.signature(method).parameters.values())
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if not parameters or parameters[0].kind not in positional or parameters[0].default is not inspect.Parameter.empty:
        raise TypeError(f"{label} must declare {shape}")
    if any(parameter.kind is not inspect.Parameter.KEYWORD_ONLY for parameter in parameters[1:]):
        raise TypeError(f"{label} must declare {shape}: configuration is keyword-only; "
                        "*args, **kwargs and extra positional parameters are not supported")
    schema = function.config_schema
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise TypeError(f"{label} must expose a Pydantic parameter contract")
    names = {parameter.name for parameter in parameters[1:]}
    fields = set(schema.model_fields)
    if names != fields:
        raise TypeError(f"{label} keyword parameters {sorted(names)} must match its parameter contract fields {sorted(fields)}")
    reserved = fields & RUNTIME_PARAMETERS
    if reserved:
        raise TypeError(f"{label} uses reserved runtime names as parameters: {sorted(reserved)}")
