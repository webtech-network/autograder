from typing import Optional
from pydantic import BaseModel, Field, JsonValue

from autograder.models.config.subject import CappedCategoryConfig, GroupConfig


class CriteriaConfig(BaseModel):
    """Root configuration for grading criteria."""

    base: GroupConfig = Field(..., description="Criteria that make up the score (0-100).")
    bonus: Optional[CappedCategoryConfig] = Field(None, description="Criteria whose score adds up to max_points.")
    penalty: Optional[CappedCategoryConfig] = Field(None, description="Criteria whose shortfall subtracts up to max_points.")

    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Free-form JSON stored with the definition; never interpreted by grading.")

    model_config = {"extra": "forbid", "allow_inf_nan": False}
