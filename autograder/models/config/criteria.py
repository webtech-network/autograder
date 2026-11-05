from typing import Optional
from pydantic import BaseModel, Field, JsonValue

from autograder.models.config.category import CategoryConfig


class CriteriaConfig(BaseModel):
    """Root configuration for grading criteria."""

    base: CategoryConfig = Field(..., description="Criteria that make up the score (weight 100).")
    bonus: Optional[CategoryConfig] = Field(None, description="Criteria whose score adds up to their weight in points.")
    penalty: Optional[CategoryConfig] = Field(None, description="Criteria whose shortfall subtracts up to their weight in points.")

    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Free-form JSON stored with the definition; never interpreted by grading.")

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    @classmethod
    def from_dict(cls, data: dict) -> "CriteriaConfig":
        """Create and validate criteria config from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> "CriteriaConfig":
        """Create and validate criteria config from JSON string."""
        return cls.model_validate_json(json_str)
