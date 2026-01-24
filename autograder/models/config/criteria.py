from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from autograder.models.config.category import CategoryConfig


class CriteriaConfig(BaseModel):
    """Root configuration for grading criteria."""

    test_library: Optional[str] = Field(
        default=None, description="Name of the test library/template to use"
    )
    base: CategoryConfig = Field(..., description="Base grading criteria (required)")
    bonus: Optional[CategoryConfig] = Field(
        default=None, description="Bonus points criteria"
    )
    penalty: Optional[CategoryConfig] = Field(
        default=None, description="Penalty criteria"
    )

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_dict(cls, data: dict) -> "CriteriaConfig":
        """Create and validate criteria config from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> "CriteriaConfig":
        """Create and validate criteria config from JSON string."""
        return cls.model_validate_json(json_str)
