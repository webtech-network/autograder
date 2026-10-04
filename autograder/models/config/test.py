"""One explicitly identified evaluator invocation; no legacy argument encodings."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    parameters: dict[str, JsonValue]
    file: str | None = Field(default=None, min_length=1)
    weight: float = Field(default=100.0, ge=0, strict=True)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
