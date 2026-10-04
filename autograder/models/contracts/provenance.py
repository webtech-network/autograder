"""Provider-independent identity of the exact normalized grading definition."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class DefinitionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference: str | None = Field(default=None, min_length=1)
    revision: int | None = Field(default=None, gt=0, strict=True)
