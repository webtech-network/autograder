"""
Pydantic models for validating criteria configuration JSON structure.

New schema structure:
- Subjects are arrays with 'subject_name' field
- Parameters are named objects: [{"name": "param", "value": "val"}, ...]
- Tests contain parameters directly (no 'calls' array)
- Root config has optional 'test_library' field
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union


class ParameterConfig(BaseModel):
    """Named parameter for a test function."""
    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value")

    model_config = {"extra": "forbid"}


class TestConfig(BaseModel):
    """Configuration for a single test execution."""
    name: str = Field(..., description="Name of the test function in the template")
    file: Optional[str] = Field(None, description="Target file for the test (if applicable)")
    parameters: Optional[List[ParameterConfig]] = Field(
        default_factory=list,
        description="Named parameters for the test function"
    )

    model_config = {"extra": "forbid"}

    def get_args_list(self) -> List[Any]:
        """Convert named parameters to positional arguments list."""
        if not self.parameters:
            return []
        return [param.value for param in self.parameters]

    def get_kwargs_dict(self) -> Dict[str, Any]:
        """Convert named parameters to keyword arguments dictionary."""
        if not self.parameters:
            return {}
        return {param.name: param.value for param in self.parameters}


class SubjectConfig(BaseModel):
    """Configuration for a subject node (can contain tests or nested subjects)."""
    subject_name: str = Field(..., description="Name of the subject")
    weight: float = Field(..., ge=0, le=100, description="Weight of this subject (0-100)")
    tests: Optional[List[TestConfig]] = Field(None, description="Tests under this subject")
    subjects: Optional[List['SubjectConfig']] = Field(None, description="Nested subjects")

    model_config = {"extra": "forbid"}

    def model_post_init(self, __context):
        """Validate that subject has either tests or subjects, but not both or neither."""
        has_tests = self.tests is not None and len(self.tests) > 0
        has_subjects = self.subjects is not None and len(self.subjects) > 0

        if has_tests and has_subjects:
            raise ValueError(f"Subject '{self.subject_name}' cannot have both 'tests' and 'subjects'. Choose one.")
        if not has_tests and not has_subjects:
            raise ValueError(f"Subject '{self.subject_name}' must have either 'tests' or 'subjects'.")


class CategoryConfig(BaseModel):
    """Configuration for a category (base, bonus, or penalty)."""
    weight: float = Field(..., ge=0, le=100, description="Weight of this category (0-100)")
    subjects: Optional[List[SubjectConfig]] = Field(None, description="Subjects under this category (array)")
    tests: Optional[List[TestConfig]] = Field(None, description="Tests directly under category")

    model_config = {"extra": "forbid"}

    def model_post_init(self, __context):
        """Validate that category has either tests or subjects."""
        has_tests = self.tests is not None and len(self.tests) > 0
        has_subjects = self.subjects is not None and len(self.subjects) > 0

        if has_tests and has_subjects:
            raise ValueError("Category cannot have both 'tests' and 'subjects'. Choose one.")
        if not has_tests and not has_subjects:
            raise ValueError("Category must have either 'tests' or 'subjects'.")


class CriteriaConfig(BaseModel):
    """Root configuration for grading criteria."""
    test_library: Optional[str] = Field(None, description="Name of the test library/template to use")
    base: CategoryConfig = Field(..., description="Base grading criteria (required)")
    bonus: Optional[CategoryConfig] = Field(None, description="Bonus points criteria")
    penalty: Optional[CategoryConfig] = Field(None, description="Penalty criteria")

    model_config = {"extra": "forbid"}

    @classmethod
    def from_dict(cls, data: dict) -> 'CriteriaConfig':
        """Create and validate criteria config from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'CriteriaConfig':
        """Create and validate criteria config from JSON string."""
        return cls.model_validate_json(json_str)
