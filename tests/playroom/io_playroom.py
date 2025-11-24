"""
Input/Output Template Playroom

This playroom demonstrates a complete grading operation for the input/output template.
It includes:
- Python program submission that accepts stdin input
- Dockerfile for containerized execution
- Setup configuration for sandbox execution
- Criteria configuration with I/O test functions
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


def create_calculator_submission():
    """Create a sample Python calculator program that accepts input."""
    return """#!/usr/bin/env python3
# Simple Calculator Program

def main():
    print("Simple Calculator")
    print("Enter first number:")
    num1 = float(input())
    
    print("Enter operation (+, -, *, /):")
    operation = input().strip()
    
    print("Enter second number:")
    num2 = float(input())
    
    if operation == '+':
        result = num1 + num2
    elif operation == '-':
        result = num1 - num2
    elif operation == '*':
        result = num1 * num2
    elif operation == '/':
        if num2 != 0:
            result = num1 / num2
        else:
            print("Error: Division by zero")
            return
    else:
        print("Error: Invalid operation")
        return
    
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
"""


def create_dockerfile():
    """Create a Dockerfile for the Python program."""
    return """FROM python:3.9-slim

WORKDIR /app

COPY calculator.py .

RUN chmod +x calculator.py

CMD ["python3", "calculator.py"]
"""


def create_setup_config():
    """Create setup configuration for I/O testing."""
    return {
        "dockerfile": "Dockerfile",
        "start_command": "python3 calculator.py",
        "build_timeout": 60,
        "execution_timeout": 10
    }


def create_criteria_config():
    """Create criteria configuration for I/O grading."""
    return {
        "Addition Test": {
            "weight": 25,
            "test": "expect_output",
            "parameters": {
                "inputs": ["10", "+", "5"],
                "expected_output": "Result: 15.0"
            }
        },
        "Subtraction Test": {
            "weight": 25,
            "test": "expect_output",
            "parameters": {
                "inputs": ["20", "-", "8"],
                "expected_output": "Result: 12.0"
            }
        },
        "Multiplication Test": {
            "weight": 25,
            "test": "expect_output",
            "parameters": {
                "inputs": ["6", "*", "7"],
                "expected_output": "Result: 42.0"
            }
        },
        "Division Test": {
            "weight": 25,
            "test": "expect_output",
            "parameters": {
                "inputs": ["100", "/", "4"],
                "expected_output": "Result: 25.0"
            }
        }
    }


def create_feedback_config():
    """Create feedback preferences for the grading."""
    return {
        "tone": "encouraging",
        "detail_level": "detailed",
        "include_suggestions": True
    }


def run_io_playroom():
    """Execute the input/output playroom."""
    print("\n" + "="*70)
    print("INPUT/OUTPUT TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Create submission files
    print("📄 Creating Python calculator submission...")
    submission_files = {
        "calculator.py": create_calculator_submission(),
        "Dockerfile": create_dockerfile()
    }

    # Create assignment configuration
    print("⚙️  Setting up assignment configuration...")
    assignment_config = AssignmentConfig(
        template="io",
        criteria=create_criteria_config(),
        feedback=create_feedback_config(),
        setup=create_setup_config()
    )

    # Create autograder request
    print("📋 Building autograder request...")
    request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="Sam Wilson",
        include_feedback=True,
        feedback_mode="default"
    )

    # Execute grading
    print("🚀 Starting grading process...")
    print("⚠️  Note: This requires Docker to be running")
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
    run_io_playroom()

