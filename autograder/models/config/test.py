"""One explicitly identified evaluator invocation; no legacy argument encodings."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TestConfig(BaseModel):
    """One criterion: an evaluator invocation with its parameters."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$", description=(
        "Stable identifier, unique in the definition; results, feedback links and comparisons use it."))
    type: str = Field(min_length=1, description="Evaluator identifier from one of the listed templates.")
    name: str = Field(min_length=1, description="Display name; may repeat.")
    parameters: dict[str, JsonValue] = Field(description=(
        "The evaluator's parameters ({} when it has none); each evaluator documents its own."))
    file: str | None = Field(default=None, min_length=1, description=(
        "Exact relative submission path to assess; null selects the evaluator's matching files."))
    weight: float = Field(default=100.0, ge=0, strict=True, description=(
        "Weight relative to sibling criteria; all-zero siblings share equally."))
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description=(
        "Free-form JSON stored with the definition; never interpreted by grading."))
