"""Deeply immutable JSON values for compiled definitions.

Compiled criteria keep their normalized parameters frozen. Evaluators and
reports receive fresh mutable copies, so no caller can alter the compiled plan
or another execution through a shared list or dictionary.
"""
from types import MappingProxyType
from typing import Any, Mapping


def freeze(value: Any) -> Any:
    """Return a deeply immutable copy of a JSON-compatible value."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Compiled values must be JSON values, not {type(value).__name__}")


def thaw(value: Any) -> Any:
    """Return a fresh mutable JSON copy that shares nothing with ``value``."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(item) for item in value]
    return value
