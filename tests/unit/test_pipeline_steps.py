"""
Unit tests for BuildTreeStep and GradeStep.

These tests verify:
1. BuildTreeStep correctly builds a CriteriaTree from config
2. GradeStep intelligently handles both CriteriaTree and Template inputs
3. Single vs multi-submission pipeline modes work correctly
"""

import sys
from pathlib import Path
from typing import List

from autograder.models.dataclass.param_description import ParamDescription
from autograder.pipeline import AutograderPipeline
from autograder.utils.printers.result_tree import ResultTreePrinter

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from autograder.steps.build_tree_step import BuildTreeStep
from autograder.steps.grade_step import GradeStep
from autograder.models.dataclass.step_result import StepStatus
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.test_result import TestResult


# Mock Template and TestFunction for testing
class MockTestFunction(TestFunction):
    """Mock test function that always passes."""

    def __init__(self, test_name):
        self._test_name = test_name

    @property
    def name(self):
        return self._test_name

    @property
    def description(self):
        return f"Mock test function: {self._test_name}"

    @property
    def parameter_description(self) -> List[ParamDescription]:
        return []

    def execute(self, *args, **kwargs):
        """Always return a passing result."""
        return TestResult(
            test_name=self._test_name,
            score=1000,
            report="Test passed",
            parameters=None
        )


class MockTemplate(Template):
    """Mock template with pre-defined test functions."""

    def __init__(self):
        self.name = "mock_template"
        self._tests = {
            "expect_output": MockTestFunction("expect_output"),
            "check_file": MockTestFunction("check_file"),
            "validate_input": MockTestFunction("validate_input"),
        }

    @property
    def template_name(self):
        """Get template name."""
        return "mock_template"

    @property
    def template_description(self):
        """Get template description."""
        return "Mock template for testing purposes"

    @property
    def requires_pre_executed_tree(self) -> bool:
        """Mock templates don't require pre-executed trees."""
        return False

    @property
    def requires_execution_helper(self) -> bool:
        """Mock templates don't require execution helpers."""
        return False

    @property
    def execution_helper(self):
        """No execution helper needed for mocks."""
        return None

    def stop(self):
        """No cleanup needed for mock templates."""
        pass

    def get_test(self, test_name: str):
        """Get a test function by name."""
        return self._tests.get(test_name)

    def get_available_tests(self):
        """Get list of available test names."""
        return list(self._tests.keys())


def create_simple_criteria():
    """Create a simple criteria configuration for testing."""
    return {
        "test_library": "input_output",
        "base": {
            "weight": 100,
            "subjects": [
                {
                    "subject_name": "Basic Tests",
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "file": "main.py",
                            "parameters": [
                                {"name": "stdin_input", "value": ["hello"]},
                                {"name": "expected_output", "value": "hello"},
                            ],
                        },
                        {
                            "name": "expect_output",
                            "file": "main.py",
                            "parameters": [
                                {"name": "stdin_input", "value": ["world"]},
                                {"name": "expected_output", "value": "world"},
                            ],
                        },
                    ],
                }
            ],
        },
        "bonus": {
            "weight": 10,
            "tests": [
                {
                    "name": "expect_output",
                    "file": "main.py",
                    "parameters": [
                        {"name": "stdin_input", "value": ["bonus"]},
                        {"name": "expected_output", "value": "bonus"},
                    ],
                }
            ],
        },
    }


def create_mock_submission():
    """Create mock submission files."""
    return {"main.py": "# Simple echo program\nprint(input())"}


def test_build_tree_step():
    """Test that BuildTreeStep correctly builds a CriteriaTree."""
    print("\n" + "=" * 80)
    print("TEST: BuildTreeStep")
    print("=" * 80)

    # Create criteria and template
    criteria = create_simple_criteria()
    template = MockTemplate()

    # Create and execute step
    build_step = BuildTreeStep(criteria)
    result = build_step.execute(template)

    # Verify result
    assert result.status == StepStatus.SUCCESS, f"Build step failed: {result.error}"
    assert result.data is not None, "CriteriaTree is None"

    criteria_tree = result.data

    # Verify tree structure
    assert criteria_tree.base is not None, "Base category missing"
    assert criteria_tree.bonus is not None, "Bonus category missing"

    print("✓ BuildTreeStep successfully built CriteriaTree")
    print(f"  - Base category: {criteria_tree.base.name}")
    print(f"  - Bonus category: {criteria_tree.bonus.name}")

    # Print tree structure
    print("\nCriteria Tree Structure:")
    criteria_tree.print_tree()

    return criteria_tree


def test_grade_from_tree():
    """Test that GradeStep can grade from a CriteriaTree."""
    print("\n" + "=" * 80)
    print("TEST: GradeStep with CriteriaTree (Multi-Submission Mode)")
    print("=" * 80)

    # Build criteria tree first
    criteria = create_simple_criteria()
    template = MockTemplate()
    build_step = BuildTreeStep(criteria)
    build_result = build_step.execute(template)

    criteria_tree = build_result.data
    submission_files = create_mock_submission()

    # Create and execute grade step
    grade_step = GradeStep(
        submission_files=submission_files)

    result = grade_step.execute(criteria_tree)

    # Verify result
    assert result.status == StepStatus.SUCCESS, f"Grade step failed: {result.error}"
    assert result.data is not None, "GradingResult is None"

    grading_result = result.data

    print("✓ GradeStep successfully graded from CriteriaTree")
    print(f"  - Final Score: {grading_result.final_score}")
    print(f"  - Status: {grading_result.status}")

    # Print result tree
    if grading_result.result_tree:
        printer = ResultTreePrinter()
        printer.print_tree(grading_result.result_tree)

    return grading_result

def test_invalid_input_type():
    """Test that GradeStep rejects invalid input types."""
    print("\n" + "=" * 80)
    print("TEST: GradeStep with Invalid Input Type")
    print("=" * 80)

    submission_files = create_mock_submission()

    grade_step = GradeStep(
        submission_files=submission_files)

    # Try to execute with invalid input (string)
    result = grade_step.execute("invalid input")

    # Verify it fails gracefully
    assert result.status == StepStatus.FAIL, "Should fail with invalid input"
    assert result.error is not None, "Should have error message"

    print("✓ GradeStep correctly rejected invalid input")
    print(f"  - Error: {result.error}")


def test_build_tree_and_grade_pipeline():
    """Test full pipeline: BuildTreeStep followed by GradeStep."""
    print("\n" + "=" * 80)
    print("TEST: Full Pipeline (BuildTreeStep + GradeStep)")
    print("=" * 80)

    # Create criteria and template
    criteria = create_simple_criteria()
    template = MockTemplate()
    submission_files = create_mock_submission()

    # Build tree
    build_step = BuildTreeStep(criteria)
    # Grade submission
    grade_step = GradeStep(
        submission_files=submission_files)

    pipeline = AutograderPipeline()
    pipeline.add_step(build_step)
    pipeline.add_step(grade_step)
    grading_result = pipeline.run(input_data=template)

    # Verify result
    assert grading_result.status == "success", f"Pipeline failed: {grading_result.error}"
    print("✓ Full pipeline successfully built tree and graded submission")
    print(f"  - Final Score: {grading_result.final_score}")

    # Print result tree
    if grading_result.result_tree:
        printer = ResultTreePrinter()
        printer.print_tree(grading_result.result_tree)
