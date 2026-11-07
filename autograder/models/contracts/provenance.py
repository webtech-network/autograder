"""Provider-independent identity of the exact normalized grading definition."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class DefinitionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    # The format of the definition the outcome is bound to. New outcomes bind
    # 2.0 definitions; outcomes recorded before the 2.0 format keep "1.0".
    schema_version: Literal["1.0", "2.0"] = Field(default="2.0", description=(
        "Format version of the bound definition snapshot."))
    definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference: str | None = Field(default=None, min_length=1)
    revision: int | None = Field(default=None, gt=0, strict=True)
