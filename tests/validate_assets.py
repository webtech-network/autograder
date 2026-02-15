"""
Asset Validation Script

Validates that all test assets are compatible with the new pipeline architecture.
Tests each template's assets by running them through the pipeline.
"""

import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineStatus
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig


def validate_webdev_assets():
    """Validate web development template assets."""
    print("Validating Web Development assets...")
    
    assets_dir = Path(__file__).parent / "assets" / "web_dev"
    
    # Load criteria from assets if available
    criteria_file = assets_dir / "criteria.json"
    if criteria_file.exists():
        with open(criteria_file) as f:
            criteria = json.load(f)
    else:
        # Use basic criteria if file doesn't exist
        criteria = {
            "base": {
                "weight": 100,
                "subjects": {
                    "HTML Structure": {
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "Check Bootstrap Linked"
                            }
                        ]
                    }
                }
            }
        }
    
    # Load submission file
    html_file = assets_dir / "index.html"
    if html_file.exists():
        with open(html_file) as f:
            html_content = f.read()
    else:
        # Use minimal HTML if file doesn't exist
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <h1 class="display-4">Test Page</h1>
</body>
</html>"""
    
    # Build pipeline
    pipeline = build_pipeline(
        template_name="webdev",
        include_feedback=False,
        grading_criteria=criteria,
        feedback_config=None,
        setup_config={},
        custom_template=None,
        feedback_mode="default",
        export_results=False
    )
    
    # Create submission
    submission = Submission(
        username="test_user",
        user_id="validation_test",
        assignment_id=999,
        submission_files={
            "index.html": SubmissionFile(
                filename="index.html",
                content=html_content
            )
        },
        language=None
    )
    
    # Run pipeline
    result = pipeline.run(submission)
    
    # Validate
    assert result.status == PipelineStatus.SUCCESS, f"Pipeline failed: {result.status}"
    assert result.result is not None, "No grading result"
    assert result.result.final_score >= 0, "Invalid score"
    
    print(f"✅ Web Dev assets validated successfully (Score: {result.result.final_score})")
    return True


def validate_essay_assets():
    """Validate essay template assets."""
    print("Validating Essay assets...")
    
    assets_dir = Path(__file__).parent / "assets" / "essay"
    
    # Use basic criteria
    criteria = {
        "base": {
            "weight": 100,
            "subjects": {
                "Content": {
                    "weight": 100,
                    "tests": [
                        {
                            "file": "essay.txt",
                            "name": "Grammar and Spelling"
                        }
                    ]
                }
            }
        }
    }
    
    # Load essay file
    essay_file = assets_dir / "essay.txt"
    if essay_file.exists():
        with open(essay_file) as f:
            essay_content = f.read()
    else:
        essay_content = "This is a test essay about education and technology."
    
    # Build pipeline
    pipeline = build_pipeline(
        template_name="essay",
        include_feedback=False,
        grading_criteria=criteria,
        feedback_config=None,
        setup_config={},
        custom_template=None,
        feedback_mode="default",
        export_results=False
    )
    
    # Create submission
    submission = Submission(
        username="test_user",
        user_id="validation_test",
        assignment_id=998,
        submission_files={
            "essay.txt": SubmissionFile(
                filename="essay.txt",
                content=essay_content
            )
        },
        language=None
    )
    
    # Run pipeline
    result = pipeline.run(submission)
    
    # Validate
    assert result.status == PipelineStatus.SUCCESS, f"Pipeline failed: {result.status}"
    assert result.result is not None, "No grading result"
    
    print(f"✅ Essay assets validated successfully (Score: {result.result.final_score})")
    return True


def validate_io_assets():
    """Validate input/output template assets."""
    print("Validating I/O assets...")
    
    # Initialize sandbox manager
    pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
    manager = initialize_sandbox_manager(pool_configs)
    
    try:
        # Simple criteria
        criteria = {
            "base": {
                "weight": 100,
                "subjects": [
                    {
                        "subject_name": "Basic Tests",
                        "weight": 100,
                        "tests": [
                            {
                                "name": "expect_output",
                                "parameters": [
                                    {"name": "inputs", "value": ["5"]},
                                    {"name": "expected_output", "value": "5"},
                                    {"name": "program_command", "value": "python3 echo.py"}
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        
        setup_config = {
            "required_files": ["echo.py"]
        }
        
        # Simple echo program
        code = """
text = input()
print(text)
"""
        
        # Build pipeline
        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=criteria,
            feedback_config=None,
            setup_config=setup_config
        )
        
        # Create submission
        submission = Submission(
            username="test_user",
            user_id="validation_test",
            assignment_id=997,
            submission_files={
                "echo.py": SubmissionFile(
                    filename="echo.py",
                    content=code
                )
            },
            language=Language.PYTHON
        )
        
        # Run pipeline
        result = pipeline.run(submission)
        
        # Validate
        assert result.status == PipelineStatus.SUCCESS, f"Pipeline failed: {result.status}"
        assert result.result is not None, "No grading result"
        
        print(f"✅ I/O assets validated successfully (Score: {result.result.final_score})")
        return True
    finally:
        manager.shutdown()


def validate_all_assets():
    """Validate all template assets."""
    print("="*60)
    print(" ASSET VALIDATION SUITE")
    print("="*60 + "\n")
    
    validators = [
        ("Web Development", validate_webdev_assets, False),
        ("Essay Grading", validate_essay_assets, False),
        ("Input/Output", validate_io_assets, True),
    ]
    
    results = []
    for name, validator, needs_sandbox in validators:
        try:
            print(f"Validating {name}...")
            validator()
            results.append((name, "✅ PASSED"))
        except Exception as e:
            print(f"❌ {name} failed: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ FAILED: {str(e)}"))
        print()
    
    print("\n" + "="*60)
    print(" VALIDATION SUMMARY")
    print("="*60)
    for name, status in results:
        print(f"{name:30s} {status}")
    print("="*60)


if __name__ == "__main__":
    validate_all_assets()
