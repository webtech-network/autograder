from typing import List, Optional
from .test import TestConfig
from pydantic import BaseModel, Field, JsonValue, model_validator


class SubjectConfig(BaseModel):
    """Configuration for a subject within a grading category."""
    subject_name: str = Field(..., min_length=1, description="Name of the subject")
    weight: float = Field(
        ..., ge=0, le=100, strict=True, description="Weight of this subject (0-100)"
    )
    tests: Optional[List[TestConfig]] = Field(
        None, description="Tests under this subject"
    )
    subjects: Optional[List["SubjectConfig"]] = Field(
        None, description="Nested subjects"
    )
    subjects_weight: Optional[float] = Field(
        None,
        strict=True,
        ge=0,
        le=100,
        description="Weight of the subject when it is a heterogeneous tree",
    )

    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    @model_validator(mode="after")
    def check_subjects_and_tests(self) -> "SubjectConfig":
        """Validate that category has at least tests or subjects."""
        has_tests = self.tests is not None and len(self.tests) > 0
        has_subjects = self.subjects is not None and len(self.subjects) > 0
        has_subject_weight = self.subjects_weight is not None

        if not has_tests and not has_subjects:
            raise ValueError("Subject must have at least 'tests' or 'subjects'.")

        if has_tests and has_subjects and not has_subject_weight:
            raise ValueError(
                "Subject needs 'subjects_weight' defined when has tests and subjects"
            )

        if not (has_tests and has_subjects) and has_subject_weight:
            raise ValueError("subjects_weight is only valid for mixed tests and subjects")

        return self
