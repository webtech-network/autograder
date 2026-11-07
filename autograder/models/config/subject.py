"""Groups of criteria: the base category, bonus/penalty categories and nested subjects.

Every group holds ``tests`` and/or ``subjects``. Sibling ``weight`` values are
ratios with one rule at every level (finite, nonnegative, unbounded); the
points a bonus or penalty category can move are its ``max_points``.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, JsonValue, model_validator

from .test import RATIO_WEIGHT, TestConfig


class GroupConfig(BaseModel):
    """A group of criteria, such as the base category: its own tests, nested subjects, or both."""
    model_config = {"extra": "forbid", "allow_inf_nan": False}

    tests: Optional[List[TestConfig]] = Field(
        None, description="Criteria directly in this group; null when it has none."
    )
    subjects: Optional[List["SubjectConfig"]] = Field(
        None, description="Subjects nested in this group; null when it has none."
    )
    subjects_weight: Optional[float] = Field(
        None,
        strict=True,
        ge=0,
        le=100,
        description="Share (0-100) of this group's score taken from its subjects when it has both tests and subjects; its tests get the rest. Required for such mixed groups and rejected otherwise.",
    )
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Free-form JSON stored with the definition; never interpreted by grading.")

    @model_validator(mode="after")
    def check_subjects_and_tests(self):
        """A group has tests or subjects; only a mixed group splits its score."""
        has_tests = bool(self.tests)
        has_subjects = bool(self.subjects)
        if not has_tests and not has_subjects:
            raise ValueError("A group must have at least 'tests' or 'subjects'.")
        if has_tests and has_subjects and self.subjects_weight is None:
            raise ValueError("A group with both tests and subjects needs 'subjects_weight'.")
        if not (has_tests and has_subjects) and self.subjects_weight is not None:
            raise ValueError("subjects_weight is only valid for mixed tests and subjects")
        return self


class _Labelled(BaseModel):
    """The label and sibling weight a subject shares with a test."""
    name: str = Field(..., min_length=1, description="Display name of the subject; may repeat.")
    weight: float = Field(default=100.0, **RATIO_WEIGHT)


class _Capped(BaseModel):
    """The points a bonus or penalty category can move."""
    max_points: float = Field(..., ge=0, le=100, strict=True, description=(
        "The most points this category adds to (bonus) or subtracts from (penalty) the base score."))


class SubjectConfig(GroupConfig, _Labelled):
    """A named group of criteria inside a category or another subject."""
    model_config = GroupConfig.model_config


class CappedCategoryConfig(GroupConfig, _Capped):
    """A bonus or penalty category: its criteria move the score by at most `max_points`."""
    model_config = GroupConfig.model_config


GroupConfig.model_rebuild()
