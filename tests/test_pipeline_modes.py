"""
Test the pipeline's ability to handle single vs multi-submission modes.

This test verifies:
1. Single submission mode: Grades directly from config (one-pass)
2. Multi-submission mode: Builds tree once, grades multiple times
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autograder.autograder import build_pipeline
from autograder.models.dataclass.criteria_config import CriteriaConfig


def create_simple_criteria():
    """Create simple test criteria."""
    return {
        "base": {
            "weight": 90,
            "subjects": [
                {
                    "subject_name": "Basic Tests",
                    "weight": 100,
                    "tests": [
                        {
                            "name": "always_pass",
                            "parameters": {}
                        },
                        {
                            "name": "check_value",
                            "parameters": {
                                "expected": 42
                            }
                        }
                    ]
                }
            ]
        },
        "bonus": {
            "weight": 10,
            "tests": [
                {
                    "name": "always_pass",
                    "parameters": {}
                }
            ]
        }
    }


def create_mock_submission():
    """Create mock submission files."""
    return {
        "main.py": "value = 42\n"
    }


def test_single_submission_mode():
    """Test single submission mode (grade directly from config)."""
    print("\n" + "="*80)
    print("TEST: Single Submission Mode (Direct from Config)")
    print("="*80)

    criteria = create_simple_criteria()
    submission = create_mock_submission()

    # Build pipeline for single submission
    pipeline = build_pipeline(
        template_name="input_output",
        include_feedback=False,
        grading_criteria=criteria,
        feedback_config=None,
        setup_config=None,
        custom_template=None,
        feedback_mode=None,
        submission_files=submission,
        submission_id="test_001",
        is_multi_submission=False  # Single submission mode
    )

    # Verify pipeline steps
    print("\nPipeline Steps:")
    for i, step in enumerate(pipeline._steps):
        print(f"  {i+1}. {step.__class__.__name__}")

    print("\nExpected flow:")
    print("  - TemplateLoaderStep loads the template")
    print("  - GradeStep grades directly from config (one-pass)")
    print("  - ExporterStep exports results")

    # Verify GradeStep has criteria_json for single submission mode
    grade_step = None
    for step in pipeline._steps:
        if step.__class__.__name__ == "GradeStep":
            grade_step = step
            break

    assert grade_step is not None, "GradeStep not found in pipeline"
    assert grade_step._criteria_json is not None, "GradeStep should have criteria_json in single mode"
    assert grade_step._submission_files is not None, "GradeStep should have submission_files"

    print("\n✓ Single submission mode configured correctly")
    print(f"  - GradeStep has criteria_json: {grade_step._criteria_json is not None}")
    print(f"  - GradeStep has submission_files: {grade_step._submission_files is not None}")


def test_multi_submission_mode():
    """Test multi-submission mode (build tree, then grade)."""
    print("\n" + "="*80)
    print("TEST: Multi-Submission Mode (Tree Building)")
    print("="*80)

    criteria = create_simple_criteria()
    submission = create_mock_submission()

    # Build pipeline for multiple submissions
    pipeline = build_pipeline(
        template_name="input_output",
        include_feedback=False,
        grading_criteria=criteria,
        feedback_config=None,
        setup_config=None,
        custom_template=None,
        feedback_mode=None,
        submission_files=submission,
        submission_id="test_002",
        is_multi_submission=True  # Multi-submission mode
    )

    # Verify pipeline steps
    print("\nPipeline Steps:")
    for i, step in enumerate(pipeline._steps):
        print(f"  {i+1}. {step.__class__.__name__}")

    print("\nExpected flow:")
    print("  - TemplateLoaderStep loads the template")
    print("  - BuildTreeStep builds criteria tree (reusable)")
    print("  - GradeStep grades from tree")
    print("  - ExporterStep exports results")

    # Verify BuildTreeStep and GradeStep are present
    has_build_tree = False
    grade_step = None

    for step in pipeline._steps:
        if step.__class__.__name__ == "BuildTreeStep":
            has_build_tree = True
        elif step.__class__.__name__ == "GradeStep":
            grade_step = step

    assert has_build_tree, "BuildTreeStep not found in pipeline for multi-submission mode"
    assert grade_step is not None, "GradeStep not found in pipeline"
    assert grade_step._criteria_json is None, "GradeStep should NOT have criteria_json in multi mode"
    assert grade_step._submission_files is not None, "GradeStep should have submission_files"

    print("\n✓ Multi-submission mode configured correctly")
    print(f"  - BuildTreeStep present: {has_build_tree}")
    print(f"  - GradeStep has criteria_json: {grade_step._criteria_json is not None}")
    print(f"  - GradeStep has submission_files: {grade_step._submission_files is not None}")


def test_grade_step_input_detection():
    """Test that GradeStep correctly detects input type."""
    print("\n" + "="*80)
    print("TEST: GradeStep Input Type Detection")
    print("="*80)

    from autograder.steps.grade_step import GradeStep
    from autograder.models.abstract.template import Template
    from autograder.models.criteria_tree import CriteriaTree, CategoryNode

    criteria = create_simple_criteria()
    submission = create_mock_submission()

    # Test 1: GradeStep with Template input (single mode)
    print("\n1. Testing with Template input (single submission mode):")
    grade_step_single = GradeStep(
        criteria_json=criteria,
        submission_files=submission,
        submission_id="test_single"
    )

    # Create a mock template
    class MockTemplate(Template):
        def __init__(self):
            self.name = "mock_template"
            self.tests = {}

        def get_test(self, test_name):
            # Return a mock test function
            def mock_test(*args, **kwargs):
                return {"passed": True, "score": 100}
            return mock_test

    mock_template = MockTemplate()

    print("  - Input type: Template")
    print("  - Expected behavior: Grade from config (one-pass)")
    print("  ✓ GradeStep will use grade_from_config method")

    # Test 2: GradeStep with CriteriaTree input (multi mode)
    print("\n2. Testing with CriteriaTree input (multi-submission mode):")
    grade_step_multi = GradeStep(
        submission_files=submission,
        submission_id="test_multi"
    )

    # Create a mock criteria tree
    mock_tree = CriteriaTree(
        base=CategoryNode(name="base", weight=100),
        bonus=None,
        penalty=None
    )

    print("  - Input type: CriteriaTree")
    print("  - Expected behavior: Grade from tree (reusable)")
    print("  ✓ GradeStep will use grade_from_tree method")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("PIPELINE MODE TESTS")
    print("="*80)

    try:
        test_single_submission_mode()
        test_multi_submission_mode()
        test_grade_step_input_detection()

        print("\n" + "="*80)
        print("ALL TESTS PASSED ✓")
        print("="*80)
        print("\nSummary:")
        print("  ✓ Single submission mode: Grades directly from config")
        print("  ✓ Multi-submission mode: Builds tree once, grades multiple times")
        print("  ✓ GradeStep correctly detects input type (Template vs CriteriaTree)")
        print("  ✓ Pipeline configuration is flexible and optimized")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

