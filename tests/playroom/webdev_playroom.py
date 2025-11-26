"""
Web Development Template Playroom

This playroom demonstrates a complete grading operation for the web development template.
It includes:
- HTML submission files with Bootstrap and CSS classes
- Criteria configuration with multiple test functions
- Feedback preferences
- Full mock grading execution
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.autograder_facade import Autograder


def create_html_submission():
    """Create a sample HTML submission with Bootstrap and CSS classes."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Portfolio</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .custom-header { background-color: #f8f9fa; }
        .custom-card { border-radius: 10px; }
    </style>
</head>
<body>
    <header class="custom-header p-4">
        <h1 class="display-4">Welcome to My Portfolio</h1>
        <p class="lead">A showcase of my work</p>
    </header>
    
    <div class="container mt-5">
        <div class="row">
            <div class="col-md-4">
                <div class="card custom-card mb-4">
                    <div class="card-body">
                        <h5 class="card-title">Project 1</h5>
                        <p class="card-text">Description of project 1</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card custom-card mb-4">
                    <div class="card-body">
                        <h5 class="card-title">Project 2</h5>
                        <p class="card-text">Description of project 2</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card custom-card mb-4">
                    <div class="card-body">
                        <h5 class="card-title">Project 3</h5>
                        <p class="card-text">Description of project 3</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="mt-5 p-4 bg-dark text-white text-center">
        <p>&copy; 2024 Student Portfolio</p>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""


def create_criteria_config():
    """Create criteria configuration for web development grading."""
    return {
        "base": {
            "weight": 100,
            "subjects": {
                "HTML Structure": {
                    "weight": 50,
                    "subjects": {
                        "Bootstrap Integration": {
                            "weight": 40,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "check_bootstrap_linked"
                                }
                            ]
                        },
                        "Bootstrap Grid Classes": {
                            "weight": 60,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["col-*"], 3]
                                    ]
                                }
                            ]
                        }
                    }
                },
                "Components": {
                    "weight": 50,
                    "subjects": {
                        "Card Components": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["card", "card-body"], 6]
                                    ]
                                }
                            ]
                        },
                        "Custom Styling": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["custom-*"], 2]
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        },
        "bonus": {
            "weight": 20,
            "subjects": {
                "Best Practices": {
                    "weight": 100,
                    "tests": [
                        {
                            "file": "index.html",
                            "name": "check_no_inline_styles"
                        }
                    ]
                }
            }
        },
        "penalty": {
            "weight": 10
        }
    }


def create_feedback_config():
    """Create feedback preferences for the grading."""
    return {
        "general": {
            "report_title": "Relatório de Avaliação - Portfolio Web",
            "show_score": True,
            "show_passed_tests": False,
            "add_report_summary": True
        },
        "ai": {
            "provide_solutions": "hint",
            "feedback_tone": "encouraging",
            "feedback_persona": "Web Development Mentor",
            "assignment_context": "Este é um projeto de portfolio web usando Bootstrap e HTML/CSS."
        },
        "default": {
            "category_headers": {
                "base": "✅ Requisitos Essenciais",
                "bonus": "⭐ Pontos Extras",
                "penalty": "❌ Pontos a Melhorar"
            }
        }
    }


def run_webdev_playroom():
    """Execute the web development playroom."""
    print("\n" + "="*70)
    print("WEB DEVELOPMENT TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Create submission files
    print("📄 Creating HTML submission...")
    submission_files = {
        "index.html": create_html_submission()
    }

    # Create assignment configuration
    print("⚙️  Setting up assignment configuration...")
    assignment_config = AssignmentConfig(
        template="webdev",
        criteria=create_criteria_config(),
        feedback=create_feedback_config(),
        setup={}
    )

    # Create autograder request
    print("📋 Building autograder request...")
    request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="John Doe",
        include_feedback=True,
        feedback_mode="default"
    )

    # Execute grading
    print("🚀 Starting grading process...\n")
    print("-"*70)
    result = Autograder.grade(request)
    print("-"*70)

    # Display results
    print("\n" + "="*70)
    print("GRADING RESULTS")
    print("="*70)
    print(f"\n✅ Status: {result.status}")
    print(f"📊 Final Score: {result.final_score}/100")
    print(f"\n📝 Feedback:\n{result.feedback}")
    print(f"\n📈 Test Report:\n{result.test_report}")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    run_webdev_playroom()

