"""Evaluator parameter contracts are validated by compilation, not tree construction."""

from typing import List, Type
from pydantic import BaseModel, Field, ValidationError
import pytest

from unittest.mock import patch

from autograder.services.criteria_tree_service import build_criteria_tree
from autograder.models.contracts.definition import DefinitionValidationError, compile_definition
from autograder.models.abstract.test_function import TestFunction
from autograder.models.abstract.template import Template


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
    def config_schema(self) -> Type[BaseModel]: return MockParams
    def execute(self, evaluation, *, required_str, optional_int=42, list_of_items=None): pass


def mock_template():
    """Mock template containing the validated test function."""
    return Template("Mock Template", "Mock", [ValidatedTestFunction()])


def definition(parameters):
    return {"schema_version": "1.0", "templates": ["mock"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [{
                "name": "Test 1", "type": "validated_test", "id": "validated-test", "parameters": parameters}]}}}


class TestCompilationValidation:
    """Evaluator contracts are enforced once, by compile_definition, never by tree construction."""

    def setup_method(self):
        self.template = mock_template()

    def test_validation_success(self):
        """Valid parameters compile and the tree carries the normalized values."""
        compiled = compile_definition(definition({"required_str": "hello", "optional_int": 100}),
                                      templates={"mock": self.template})
        assert dict(compiled.criteria_tree.base.tests[0].parameters) == {
            "required_str": "hello", "optional_int": 100, "list_of_items": ()}

    def test_validation_failure_missing_field(self):
        """Missing required fields are reported at their JSON path."""
        with pytest.raises(DefinitionValidationError) as excinfo:
            compile_definition(definition({"optional_int": 10}), templates={"mock": self.template})
        assert excinfo.value.errors()[0]["path"][-2:] == ["parameters", "required_str"]

    def test_validation_failure_wrong_type(self):
        """Incorrect field types are reported at their JSON path."""
        with pytest.raises(DefinitionValidationError) as excinfo:
            compile_definition(definition({"required_str": "hello", "optional_int": "not-an-int"}),
                               templates={"mock": self.template})
        assert excinfo.value.errors()[0]["path"][-2:] == ["parameters", "optional_int"]

    def test_tree_construction_does_not_validate_again(self):
        """Building the tree consumes compiled values and never re-runs the contract."""
        compiled = compile_definition(definition({"required_str": "hello"}), templates={"mock": self.template})
        with patch.object(MockParams, "model_validate", side_effect=AssertionError("second validation")):
            tree = build_criteria_tree(compiled.definition.criteria, {"validated_test": ValidatedTestFunction()})
        assert tree.base.tests[0].parameters["required_str"] == "hello"
