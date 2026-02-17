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

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineStatus


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
                                    "name": "Check Bootstrap Linked"
                                }
                            ]
                        },
                        "Bootstrap Grid Classes": {
                            "weight": 60,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "Has Class",
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
                                    "name": "Has Class",
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
                                    "name": "Has Class",
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
                            "name": "Check no Inline Styles"
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

def print_result_tree(node, indent=0):
    """
    Recursively prints the result tree in a hierarchical format.
  
    """
    prefix = "  " * indent
    score_str = f"{node.weighted_score:.2f}" if node.weighted_score is not None else "N/A"
    
    # Based on the level, choose an icon
    if indent == 0:
        icon = "🌳"
    elif indent == 1:
        icon = "📁"
    else:
        icon = "📘"
    
    
    weight_str = f" (w={node.weight:.1f})" if node.weight > 0 else ""
    test_str = f" [{node.total_test} tests]" if hasattr(node, 'total_test') and node.total_test > 0 else ""
    
      # Show unwweughted score if different than weighted score
    if node.unweighted_score and node.weighted_score != node.unweighted_score:
        score_str += f" (raw: {node.unweighted_score:.2f})"
    
    print(f"{prefix}{icon} {node.name}{weight_str}: {score_str}{test_str}")
    
    # Children recursion
    for child in node.children:
        print_result_tree(child, indent + 1)



def run_webdev_playroom():
    """Execute the web development playroom."""
    print("\n" + "="*70)
    print("WEB DEVELOPMENT TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Create submission files
    print("📄 Creating HTML submission...")
    submission_files = {
        "index.html": SubmissionFile(
            filename="index.html",
            content=create_html_submission()
        )
    }

    # Build pipeline
    print("⚙️  Building grading pipeline...")
    pipeline = build_pipeline(
        template_name="webdev",
        include_feedback=True,
        grading_criteria=create_criteria_config(),
        feedback_config=create_feedback_config(),
        setup_config={},
        custom_template=None,
        feedback_mode="default",
        export_results=False
    )

    # Create submission
    print("📋 Creating submission...")
    submission = Submission(
        username="John Doe",
        user_id="student123",
        assignment_id=1,
        submission_files=submission_files,
        language=None  # Not needed for webdev template
    )

    # Execute grading
    print("🚀 Starting grading process...\n")
    print("-"*70)
    pipeline_execution = pipeline.run(submission)
    print("-"*70)

    print("\n" + "=" * 70)
    print("          HIERARCHICAL RESULT TREE")
    print("=" * 70 + "\n")

    if pipeline_execution.result and hasattr(pipeline_execution.result, 'result_tree') and pipeline_execution.result.result_tree:
        # Prints the result tree
        print_result_tree(pipeline_execution.result.result_tree)

    # Display results
    print("\n" + "="*70)
    print("GRADING RESULTS")
    print("="*70)
    print(f"\n✅ Status: {pipeline_execution.status.value}")
    
    if pipeline_execution.result:
        print(f"📊 Final Score: {pipeline_execution.result.final_score}/100")
        if hasattr(pipeline_execution.result, 'feedback') and pipeline_execution.result.feedback:
            print(f"\n📝 Feedback:\n{pipeline_execution.result.feedback}")
        if hasattr(pipeline_execution.result, 'test_report') and pipeline_execution.result.test_report:
            print(f"\n📈 Test Report:\n{pipeline_execution.result.test_report}")
    else:
        print("❌ No grading result available")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    run_webdev_playroom()

