"""
API Testing Template Playroom

This playroom demonstrates a complete grading operation for the API testing template.
It includes:
- Flask API submission files
- Dockerfile for containerization
- Setup configuration for sandbox execution
- Criteria configuration with API test functions
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
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig


def create_api_submission():
    """Create a sample Flask API submission."""
    return """from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory data store
users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
]

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(users), 200

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        return jsonify(user), 200
    return jsonify({"error": "User not found"}), 404

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_user = {
        "id": len(users) + 1,
        "name": data.get("name"),
        "email": data.get("email")
    }
    users.append(new_user)
    return jsonify(new_user), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
"""


def create_dockerfile():
    """Create a Dockerfile for the API."""
    return """FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
"""


def create_requirements_txt():
    """Create requirements file for the API."""
    return """Flask==2.3.0
Werkzeug==2.3.0
"""


def create_setup_config():
    """Create setup configuration for API testing."""
    return {
        "runtime_image": "python:3.9-slim",
        "container_port": 5000,
        "start_command": "python app.py",
        "commands": {
            "install_dependencies": "pip install Flask==2.3.0 Werkzeug==2.3.0"
        }
    }


def create_criteria_config():
    """Create criteria configuration for API grading."""
    return {
        "base": {
            "weight": 100,
            "subjects": {
                "API Endpoints": {
                    "weight": 100,
                    "subjects": {
                        "Health Check": {
                            "weight": 30,
                            "tests": [
                                {
                                    "name": "Health Check",
                                    "calls": [
                                        ["/health"]
                                    ]
                                }
                            ]
                        },
                        "Get All Users": {
                            "weight": 35,
                            "tests": [
                                {
                                    "name": "Check Response JSON",
                                    "calls": [
                                        ["/api/users", "0", {"id": 1}]
                                    ]
                                }
                            ]
                        },
                        "Get Single User": {
                            "weight": 35,
                            "tests": [
                                {
                                    "name": "Check Response JSON",
                                    "calls": [
                                        ["/api/users/1", "id", 1],
                                        ["/api/users/1", "name", "Alice"]
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
                "Advanced Features": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "Check Response JSON",
                            "calls": [
                                ["/api/users/2", "email", "bob@example.com"]
                            ]
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
            "report_title": "Relatório de Avaliação - API REST",
            "show_score": True,
            "show_passed_tests": False,
            "add_report_summary": True
        },
        "ai": {
            "provide_solutions": "hint",
            "feedback_tone": "professional",
            "feedback_persona": "Senior Backend Developer",
            "assignment_context": "Este é um teste de API REST com Flask."
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



def run_api_playroom():
    """Execute the API testing playroom."""
    print("\n" + "="*70)
    print("API TESTING TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Initialize sandbox manager
    print("🔧 Initializing sandbox manager...")
    pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
    manager = initialize_sandbox_manager(pool_configs)
    print("✅ Sandbox manager ready\n")

    try:
        # Create submission files
        print("📄 Creating API submission files...")
        submission_files = {
            "app.py": SubmissionFile(
                filename="app.py",
                content=create_api_submission()
            )
        }

        # Build pipeline
        print("⚙️  Building grading pipeline...")
        pipeline = build_pipeline(
            template_name="api",
            include_feedback=True,
            grading_criteria=create_criteria_config(),
            feedback_config=create_feedback_config(),
            setup_config=create_setup_config(),
            custom_template=None,
            feedback_mode="default",
            export_results=False
        )

        # Create submission
        print("📋 Creating submission...")
        submission = Submission(
            username="Jane Smith",
            user_id="student456",
            assignment_id=2,
            submission_files=submission_files,
            language=Language.NODE  # Required for API template
        )

        # Execute grading
        print("🚀 Starting grading process...")
        print("⚠️  Note: This requires Docker to be running and may take a few minutes")
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

    finally:
        # Cleanup
        print("\n🧹 Cleaning up sandbox manager...")
        manager.shutdown()
        print("✅ Cleanup complete\n")


if __name__ == "__main__":
    run_api_playroom()

