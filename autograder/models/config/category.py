from typing import List, Optional

from autograder.models.config.subject import SubjectConfig
from .test import TestConfig
from pydantic import BaseModel, Field, model_validator


class CategoryConfig(BaseModel):
    weight: float = Field(
        ..., ge=0, le=100, description="Weight of this category (0-100)"
    )
    tests: Optional[List[TestConfig]] = Field(
        None, description="Tests under this subject"
    )
    subjects: Optional[List[SubjectConfig]] = Field(None, description="Nested subjects")
    subjects_weight: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Weight of the subject when it is a heterogeneous tree",
    )

    model_config = {"extra": "forbid"}

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

        return self
