"""Derive evaluator contracts from their annotated implementation signatures."""
import inspect
from typing import Annotated, Any, get_type_hints
from pydantic import BaseModel, ConfigDict, Field, create_model

RUNTIME_PARAMETERS = frozenset({"files", "sandbox", "submission_files", "submission_language",
    "structural_analysis", "locale", "evaluation_scope", "file_metadata", "pre_computed_results", "criterion_id", "precomputed_results"})


def signature_contract(function) -> type[BaseModel]:
    """A keyword evaluator may supply config_schema; signatures cover ordinary ones."""
    hints = get_type_hints(type(function).execute)
    fields = {}
    for name, parameter in inspect.signature(function.execute).parameters.items():
        if name in RUNTIME_PARAMETERS or parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        annotation = hints.get(name, Any)
        default = parameter.default
        if annotation is list:
            annotation = list[str]
        if default is inspect.Parameter.empty:
            default = ...
        elif default is None:
            # Lists use actual executable defaults, never normalize back to null.
            if getattr(annotation, '__origin__', None) is list:
                default = Field(default_factory=list)
            elif annotation is Any:
                default = None
        if annotation is str:
            annotation = Annotated[str, Field(min_length=1)]
            if default == "":
                default = ...
        if annotation in (int, float):
            annotation = Annotated[annotation, Field(ge=0)]
        fields[name] = (annotation, default)
    return create_model(type(function).__name__ + "Parameters", __config__=ConfigDict(
        extra="forbid", strict=True, allow_inf_nan=False), **fields)
