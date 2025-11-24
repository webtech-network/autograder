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

from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.autograder_facade import Autograder


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
        "dockerfile": "Dockerfile",
        "container_port": 5000,
        "start_command": "python app.py",
        "build_timeout": 120,
        "startup_wait": 3
    }


def create_criteria_config():
    """Create criteria configuration for API grading."""
    return {
        "Health Endpoint": {
            "weight": 20,
            "test": "health_check",
            "parameters": {
                "endpoint": "/health"
            }
        },
        "Get All Users": {
            "weight": 25,
            "test": "check_endpoint_response",
            "parameters": {
                "endpoint": "/api/users",
                "method": "GET",
                "expected_status": 200
            }
        },
        "Get Single User": {
            "weight": 25,
            "test": "check_endpoint_response",
            "parameters": {
                "endpoint": "/api/users/1",
                "method": "GET",
                "expected_status": 200
            }
        },
        "Create User": {
            "weight": 30,
            "test": "check_post_endpoint",
            "parameters": {
                "endpoint": "/api/users",
                "payload": {"name": "Charlie", "email": "charlie@example.com"},
                "expected_status": 201
            }
        }
    }


def create_feedback_config():
    """Create feedback preferences for the grading."""
    return {
        "tone": "professional",
        "detail_level": "detailed",
        "include_suggestions": True
    }


def run_api_playroom():
    """Execute the API testing playroom."""
    print("\n" + "="*70)
    print("API TESTING TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Create submission files
    print("📄 Creating API submission files...")
    submission_files = {
        "app.py": create_api_submission(),
        "Dockerfile": create_dockerfile(),
        "requirements.txt": create_requirements_txt()
    }

    # Create assignment configuration
    print("⚙️  Setting up assignment configuration...")
    assignment_config = AssignmentConfig(
        template="api",
        criteria=create_criteria_config(),
        feedback=create_feedback_config(),
        setup=create_setup_config()
    )

    # Create autograder request
    print("📋 Building autograder request...")
    request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="Jane Smith",
        include_feedback=True,
        feedback_mode="default"
    )

    # Execute grading
    print("🚀 Starting grading process...")
    print("⚠️  Note: This requires Docker to be running and may take a few minutes")
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
    run_api_playroom()

