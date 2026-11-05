from typing import List, Optional

from autograder.models.config.subject import SubjectConfig
from .test import TestConfig
from pydantic import BaseModel, Field, JsonValue, model_validator


class CategoryConfig(BaseModel):
    """Configuration for a grading category (base, bonus, or penalty)."""
    weight: float = Field(
        ..., ge=0, le=100, strict=True, description="Base must be 100; bonus and penalty weights (0-100) cap the points they add or subtract."
    )
    tests: Optional[List[TestConfig]] = Field(
        None, description="Criteria directly under this category; null when it has none."
    )
    subjects: Optional[List[SubjectConfig]] = Field(None, description="Subjects nested in this category; null when it has none.")
    subjects_weight: Optional[float] = Field(
        None,
        strict=True,
        ge=0,
        le=100,
        description="Share (0-100) of this group's score taken from its subjects when it has both tests and subjects; its tests get the rest. Required for such mixed groups and rejected otherwise.",
    )

    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Free-form JSON stored with the definition; never interpreted by grading.")

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    @model_validator(mode="after")
    def check_subjects_and_tests(self) -> "CategoryConfig":
        """Validate that category has at least tests or subjects."""
        has_tests = self.tests is not None and len(self.tests) > 0
        has_subjects = self.subjects is not None and len(self.subjects) > 0
        has_subject_weight = self.subjects_weight is not None

        if not has_tests and not has_subjects:
            raise ValueError("Category must have at least 'tests' or 'subjects'.")

        if has_tests and has_subjects and not has_subject_weight:
            raise ValueError(
                "Category needs 'subjects_weight' defined when has tests and subjects"
            )

        if not (has_tests and has_subjects) and has_subject_weight:
            raise ValueError("subjects_weight is only valid for mixed tests and subjects")

        return self
