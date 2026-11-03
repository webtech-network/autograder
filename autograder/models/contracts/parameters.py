"""Shared parameter types reused by several evaluator-owned contracts."""
from typing import Annotated, Literal
from pydantic import Field

Nonempty = Annotated[str, Field(min_length=1)]
LanguageId = Literal["python", "java", "node", "cpp", "c"]
Command = Nonempty | dict[LanguageId, Nonempty]
