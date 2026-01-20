"""
Simple test script for grading an HTML assignment using the autograder pipeline.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile


def create_mock_html_submission():
    """Create a mock HTML submission for testing."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Portfolio</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="container">
        <h1>John Doe - Portfolio</h1>
        <nav>
            <a href="#about">About</a>
            <a href="#projects">Projects</a>
        </nav>
    </header>

    <div class="container row">
        <div class="col-md-6">
            <h1>Welcome</h1>
            <p>This is my portfolio website showcasing my work.</p>
            <p>I'm a passionate developer with experience in web technologies.</p>
            <p>Check out my projects below!</p>
        </div>
        <div class="col-md-6">
            <div class="card">
                <h2>About Me</h2>
                <p>I love coding and creating amazing web experiences.</p>
            </div>
        </div>
    </div>

    <footer class="container">
        <p>&copy; 2024 John Doe</p>
    </footer>

    <script src="script.js"></script>
</body>
</html>"""

    submission_file = SubmissionFile(
        filename="index.html",
        content=html_content
    )

    submission = Submission(
        username="student123",
        user_id=12345,
        assignment_id=1,
        submission_files=[submission_file]
    )

    return submission


def create_mock_grading_criteria():
    """Create mock grading criteria for HTML assignment."""
    return {
        "base": {
            "weight": 100,
            "subjects": {
                "html_structure": {
                    "weight": 40,
                    "tests": [
                        {
                            "name": "has_tag",
                            "file": "index.html",
                            "calls": [
                                ["div", 5],
                                ["h1", 2],
                                ["p", 3],
                                ["a", 2]
                            ]
                        }
                    ]
                },
                "css_styling": {
                    "weight": 30,
                    "tests": [
                        {
                            "name": "has_class",
                            "file": "index.html",
                            "calls": [
                                [["container", "row", "col-*"], 10]
                            ]
                        }
                    ]
                }
            }
        }
    }


def create_mock_feedback_config():
    """Create mock feedback configuration."""
    return {
        "general": {
            "report_title": "Web Development Assignment Feedback",
            "show_score": True,
            "show_passed_tests": False,
            "add_report_summary": True
        },
        "default": {
            "category_headers": {
                "base": "Core Web Development Requirements",
                "html_structure": "HTML Structure & Semantics",
                "css_styling": "CSS Styling & Design"
            }
        }
    }


def html_grading_pipeline():
    """Test the autograder pipeline with HTML assignment."""
    print("\n" + "="*70)
    print("HTML ASSIGNMENT GRADING TEST")
    print("="*70 + "\n")

    # Create mock data
    print("📄 Creating mock HTML submission...")
    submission = create_mock_html_submission()

    print("⚙️  Creating grading criteria...")
    grading_criteria = create_mock_grading_criteria()

    print("📋 Creating feedback configuration...")
    feedback_config = create_mock_feedback_config()

    # Build the pipeline
    print("🔧 Building autograder pipeline...")
    pipeline = build_pipeline(
        template_name="webdev",
        include_feedback=False,  # Set to True to include feedback generation
        grading_criteria=grading_criteria,
        feedback_config=feedback_config,
        setup_config=None,
        custom_template=None,
        feedback_mode=None,
        submission_files={sf.filename: sf.content for sf in submission.submission_files}
    )

    print("✅ Pipeline built successfully!\n")
    print("Pipeline steps:")
    for i, step in enumerate(pipeline._steps, 1):
        print(f"  {i}. {step.__class__.__name__}")

    print("\n" + "="*70)
    print("Pipeline is ready. You can now implement the rest!")
    print("="*70 + "\n")

    return pipeline


if __name__ == "__main__":
    pipeline = html_grading_pipeline()

    pipeline.run(create_mock_html_submission())

