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

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineStatus
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig


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

    # Initialize sandbox manager
    print("🔧 Initializing sandbox manager...")
    pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
    manager = initialize_sandbox_manager(pool_configs)
    print("✅ Sandbox manager ready\n")

    try:
        # Create submission files
        print("📄 Creating Python calculator submission...")
        submission_files = {
            "calculator.py": SubmissionFile(
                filename="calculator.py",
                content=create_calculator_submission()
            )
        }

        # Build pipeline
        print("⚙️  Building grading pipeline...")
        pipeline = build_pipeline(
            template_name="IO",
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
            username="Sam Wilson",
            user_id="student789",
            assignment_id=3,
            submission_files=submission_files,
            language=Language.PYTHON  # Required for I/O template
        )

        # Execute grading
        print("🚀 Starting grading process...")
        print("⚠️  Note: This requires Docker to be running")
        print("-"*70)
        pipeline_execution = pipeline.run(submission)
        print("-"*70)

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
    run_io_playroom()

