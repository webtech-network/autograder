"""
Sandbox Manager Integration Example

Demonstrates the complete workflow of:
1. Initializing the sandbox manager
2. Creating a sandbox
3. Preparing workdir with files
4. Running commands
5. Making HTTP requests
6. Releasing the sandbox

This is a reference implementation for understanding how the sandbox manager
integrates with the autograder pipeline.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from autograder.models.dataclass.submission import Submission, SubmissionFile


def example_1_simple_command_execution():
    """
    Example 1: Execute a simple Python script
    """
    print("=" * 60)
    print("Example 1: Simple Command Execution")
    print("=" * 60)

    # Initialize sandbox manager (done once at startup)
    pool_configs = [
        SandboxPoolConfig(
            language=Language.PYTHON,
            pool_size=2,
            scale_limit=5,
            idle_timeout=300,
            running_timeout=60
        )
    ]
    initialize_sandbox_manager(pool_configs)

    # Get manager instance
    manager = get_sandbox_manager()

    # Acquire a sandbox
    sandbox = manager.get_sandbox(Language.PYTHON)
    print(f"Acquired sandbox: {sandbox}")

    # Prepare files
    submission_files = {
        "hello.py": SubmissionFile("hello.py", "print('Hello from sandbox!')")
    }
    sandbox.prepare_workdir(submission_files)
    print("Workdir prepared with hello.py")

    # Execute command
    response = sandbox.run_command("python3 hello.py")
    print(f"Exit Code: {response.exit_code}")
    print(f"Output: {response.stdout}")
    print(f"Execution Time: {response.execution_time:.3f}s")

    # Release sandbox back to pool
    manager.release_sandbox(Language.PYTHON, sandbox)
    print("Sandbox released")


def example_2_interactive_calculator():
    """
    Example 2: Interactive calculator with batch input
    """
    print("\n" + "=" * 60)
    print("Example 2: Interactive Calculator")
    print("=" * 60)

    manager = get_sandbox_manager()
    sandbox = manager.get_sandbox(Language.PYTHON)

    # Calculator code
    calculator_code = """
import sys

def main():
    operation = input().strip()
    num1 = float(input())
    num2 = float(input())
    
    if operation == 'ADD':
        print(num1 + num2)
    elif operation == 'SUB':
        print(num1 - num2)
    elif operation == 'MUL':
        print(num1 * num2)
    elif operation == 'DIV':
        if num2 != 0:
            print(num1 / num2)
        else:
            print("Error: Division by zero")

if __name__ == "__main__":
    main()
"""

    submission_files = {
        "calculator.py": SubmissionFile("calculator.py", calculator_code)
    }
    sandbox.prepare_workdir(submission_files)

    # Test addition
    response = sandbox.run_commands(
        commands=["ADD", "10", "20"],
        program_command="python3 calculator.py"
    )
    print(f"ADD 10 + 20 = {response.stdout.strip()}")

    manager.release_sandbox(Language.PYTHON, sandbox)


def example_3_nested_directory_structure():
    """
    Example 3: Project with nested directory structure
    """
    print("\n" + "=" * 60)
    print("Example 3: Nested Directory Structure")
    print("=" * 60)

    manager = get_sandbox_manager()
    sandbox = manager.get_sandbox(Language.PYTHON)

    # Simulate a project with multiple directories
    submission_files = {
        "main.py": SubmissionFile("main.py",
            "from services.user_service import UserService\n"
            "from models.user import User\n"
            "print('Imports successful!')"
        ),
        "services/user_service.py": SubmissionFile(
            "services/user_service.py",
            "class UserService:\n    pass"
        ),
        "services/__init__.py": SubmissionFile("services/__init__.py", ""),
        "models/user.py": SubmissionFile(
            "models/user.py",
            "class User:\n    pass"
        ),
        "models/__init__.py": SubmissionFile("models/__init__.py", "")
    }

    sandbox.prepare_workdir(submission_files)
    print("Created directory structure:")
    print("  /app/main.py")
    print("  /app/services/user_service.py")
    print("  /app/services/__init__.py")
    print("  /app/models/user.py")
    print("  /app/models/__init__.py")

    # Verify imports work
    response = sandbox.run_command("python3 main.py")
    print(f"\nExecution result: {response.stdout.strip()}")
    print(f"Exit code: {response.exit_code}")

    manager.release_sandbox(Language.PYTHON, sandbox)


def example_4_leetcode_style_problem():
    """
    Example 4: LeetCode-style two sum problem
    """
    print("\n" + "=" * 60)
    print("Example 4: LeetCode-style Problem (Two Sum)")
    print("=" * 60)

    manager = get_sandbox_manager()
    sandbox = manager.get_sandbox(Language.PYTHON)

    # Two Sum solution
    solution_code = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Read input
import json
nums = json.loads(input())
target = int(input())

# Solve and print result
result = two_sum(nums, target)
print(json.dumps(result))
"""

    submission_files = {
        "solution.py": SubmissionFile("solution.py", solution_code)
    }
    sandbox.prepare_workdir(submission_files)

    # Test case 1: [2,7,11,15], target=9
    response = sandbox.run_commands(
        commands=["[2,7,11,15]", "9"],
        program_command="python3 solution.py"
    )
    print(f"Input: nums=[2,7,11,15], target=9")
    print(f"Output: {response.stdout.strip()}")

    # Test case 2: [3,2,4], target=6
    sandbox2 = manager.get_sandbox(Language.PYTHON)
    sandbox2.prepare_workdir(submission_files)
    response = sandbox2.run_commands(
        commands=["[3,2,4]", "6"],
        program_command="python3 solution.py"
    )
    print(f"\nInput: nums=[3,2,4], target=6")
    print(f"Output: {response.stdout.strip()}")

    manager.release_sandbox(Language.PYTHON, sandbox)
    manager.release_sandbox(Language.PYTHON, sandbox2)


def example_5_error_handling():
    """
    Example 5: Proper error handling
    """
    print("\n" + "=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)

    manager = get_sandbox_manager()
    sandbox = manager.get_sandbox(Language.PYTHON)

    # Code with syntax error
    buggy_code = """
def buggy_function():
    print("Missing closing parenthesis"
    
buggy_function()
"""

    submission_files = {
        "buggy.py": SubmissionFile("buggy.py", buggy_code)
    }
    sandbox.prepare_workdir(submission_files)

    # Execute and capture error
    response = sandbox.run_command("python3 buggy.py")

    print(f"Exit Code: {response.exit_code}")
    print(f"Stdout: {response.stdout}")
    print(f"Stderr: {response.stderr}")

    if response.exit_code != 0:
        print("\n✗ Execution failed (as expected)")
        print("Error message can be shown to student for debugging")

    manager.release_sandbox(Language.PYTHON, sandbox)


def example_6_timeout_handling():
    """
    Example 6: Handling timeouts
    """
    print("\n" + "=" * 60)
    print("Example 6: Timeout Handling")
    print("=" * 60)

    manager = get_sandbox_manager()
    sandbox = manager.get_sandbox(Language.PYTHON)

    # Infinite loop code
    infinite_loop = """
while True:
    pass
"""

    submission_files = {
        "loop.py": SubmissionFile("loop.py", infinite_loop)
    }
    sandbox.prepare_workdir(submission_files)

    print("Running program with 2-second timeout...")
    # Note: Docker exec_run timeout is not perfect, but we track execution time
    import time
    start = time.time()

    # In production, you'd want better timeout handling
    # This is a simplified example
    response = sandbox.run_command("timeout 2 python3 loop.py", timeout=3)

    elapsed = time.time() - start
    print(f"Execution stopped after {elapsed:.2f}s")
    print(f"Exit code: {response.exit_code}")

    manager.release_sandbox(Language.PYTHON, sandbox)


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "SANDBOX MANAGER INTEGRATION EXAMPLES" + " " * 12 + "║")
    print("╚" + "═" * 58 + "╝")

    try:
        example_1_simple_command_execution()
        print("\n" + "=" * 60)
        example_2_interactive_calculator()
        example_3_nested_directory_structure()
        example_4_leetcode_style_problem()
        example_5_error_handling()
        example_6_timeout_handling()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n⚠ Error running examples: {e}")
        print("Note: These examples require Docker and gVisor runtime to be installed")
        print("Run 'make sandbox-setup' to configure the environment")

