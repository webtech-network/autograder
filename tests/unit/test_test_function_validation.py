"""Tests for TestFunction parameter validation in CriteriaTreeService."""

from typing import List, Optional, Type
from pydantic import BaseModel, Field, ValidationError
import pytest

from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.models.abstract.test_function import TestFunction
from autograder.models.abstract.template import Template
from autograder.models.config.test import TestConfig
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.config.category import CategoryConfig


class MockParams(BaseModel):
    """Mock Pydantic model for testing validation."""
    required_str: str
    optional_int: int = 42
    list_of_items: List[str] = Field(default_factory=list)


class ValidatedTestFunction(TestFunction):
    """A mock test function that provides a config schema."""
    @property
    def name(self): return "validated_test"
    @property
    def description(self): return "A test with validation"
    @property
    def parameter_description(self): return []
    @property
    def config_schema(self) -> Type[BaseModel]: return MockParams
    def execute(self, files, sandbox, *args, **kwargs): pass


class MockTemplate(Template):
    """Mock template containing the validated test function."""
    def __init__(self):
        self.tests = {"validated_test": ValidatedTestFunction()}
    @property
    def template_name(self): return "Mock Template"
    @property
    def template_description(self): return "Mock"
    @property
    def requires_sandbox(self): return False
    def get_test(self, name): return self.tests.get(name)


class TestCriteriaTreeServiceValidation:
    """Test suite for early validation logic in CriteriaTreeService."""

    def setup_method(self):
        self.service = CriteriaTreeService()
        self.template = MockTemplate()

    def test_validation_success(self):
        """Test that valid parameters pass validation during tree building."""
        criteria_dict = {
            "base": {
                "weight": 100,
                "tests": [
                    {
                        "name": "Test 1",
                        "type": "validated_test",
                        "parameters": [
                            {"name": "required_str", "value": "hello"},
                            {"name": "optional_int", "value": 100}
                        ]
                    }
                ]
            }
        }
        config = CriteriaConfig.from_dict(criteria_dict)
        # Should NOT raise ValueError
        tree = self.service.build_tree(config, self.template)
        assert tree is not None
        assert tree.base.tests[0].parameters["required_str"] == "hello"

    def test_validation_failure_missing_field(self):
        """Test that missing required fields raise ValueError."""
        criteria_dict = {
            "base": {
                "weight": 100,
                "tests": [
                    {
                        "name": "Test Fail",
                        "type": "validated_test",
                        "parameters": [
                            {"name": "optional_int", "value": 10}
                        ]
                    }
                ]
            }
        }
        config = CriteriaConfig.from_dict(criteria_dict)
        with pytest.raises(ValueError) as excinfo:
            self.service.build_tree(config, self.template)
        
        assert "Invalid parameters" in str(excinfo.value)
        assert "required_str" in str(excinfo.value)

    def test_validation_failure_wrong_type(self):
        """Test that incorrect field types raise ValueError."""
        criteria_dict = {
            "base": {
                "weight": 100,
                "tests": [
                    {
                        "name": "Test Fail Type",
                        "type": "validated_test",
                        "parameters": [
                            {"name": "required_str", "value": "hello"},
                            {"name": "optional_int", "value": "not-an-int"}
                        ]
                    }
                ]
            }
        }
        config = CriteriaConfig.from_dict(criteria_dict)
        with pytest.raises(ValueError) as excinfo:
            self.service.build_tree(config, self.template)
        
        assert "Invalid parameters" in str(excinfo.value)
        assert "optional_int" in str(excinfo.value)
