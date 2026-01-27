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


def create_setup_config():
    """Create setup configuration for I/O testing."""
    return {
        "runtime_image": "python:3.9-slim",
        "container_port": None,  # No port mapping needed for I/O testing
        "execution_timeout": 10,
        "start_command": "python3 calculator.py"
    }


def create_criteria_config():
    """Create criteria configuration for I/O grading."""
    return {
        "base": {
            "weight": 100,
            "subjects": {
                "Basic Operations": {
                    "weight": 100,
                    "subjects": {
                        "Addition": {
                            "weight": 25,
                            "tests": [
                                {
                                    "name": "Expect Output",
                                    "calls": [
                                        [["10", "+", "5"], "Result: 15.0"]
                                    ]
                                }
                            ]
                        },
                        "Subtraction": {
                            "weight": 25,
                            "tests": [
                                {
                                    "name": "Expect Output",
                                    "calls": [
                                        [["20", "-", "8"], "Result: 12.0"]
                                    ]
                                }
                            ]
                        },
                        "Multiplication": {
                            "weight": 25,
                            "tests": [
                                {
                                    "name": "Expect Output",
                                    "calls": [
                                        [["6", "*", "7"], "Result: 42.0"]
                                    ]
                                }
                            ]
                        },
                        "Division": {
                            "weight": 25,
                            "tests": [
                                {
                                    "name": "Expect Output",
                                    "calls": [
                                        [["100", "/", "4"], "Result: 25.0"]
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
                "Error Handling": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "Expect Output",
                            "calls": [
                                [["10", "/", "0"], "Error: Division by zero"]
                            ]
                        }
                    ]
                }
            }
        }
    }


def create_feedback_config():
    """Create feedback preferences for the grading."""
    return {
        "general": {
            "report_title": "Relatório de Avaliação - Calculadora",
            "show_score": True,
            "show_passed_tests": False,
            "add_report_summary": True
        },
        "ai": {
            "provide_solutions": "hint",
            "feedback_tone": "encouraging but direct",
            "feedback_persona": "Code Buddy",
            "assignment_context": "Este é um teste de programa interativo com entrada/saída."
        },
        "default": {
            "category_headers": {
                "base": "✅ Requisitos Essenciais",
                "bonus": "⭐ Pontos Extras"
            }
        }
    }


def run_io_playroom():
    """Execute the input/output playroom."""
    print("\n" + "="*70)
    print("INPUT/OUTPUT TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Create submission files
    print("📄 Creating Python calculator submission...")
    submission_files = {
        "calculator.py": create_calculator_submission()
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

