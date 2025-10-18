import time
import json

from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult
from autograder.builder.execution_helpers.sandbox_executor import SandboxExecutor


# ===============================================================
# region: TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(TestFunction):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.
    """

    @property
    def name(self):
        return "expect_output"

    @property
    def description(self):
        return "Runs the student's program, feeds it a series of line-separated inputs, and checks if the final output is correct."

    @property
    def parameter_description(self):
        return {
            "inputs": "A list of strings to be sent to the program, each on a new line.",
            "expected_output": "The single, exact string the program is expected to print to standard output."
        }

    def __init__(self, executor: SandboxExecutor):
        self.executor = executor

    def execute(self, inputs: list, expected_output: str) -> TestResult:
        """
        Constructs and runs the command using file redirection for robust input handling,
        then validates the output.
        """
        start_command = self.executor.config.get("start_command")
        if not start_command:
            raise ValueError("A 'start_command' must be defined in setup.json for this template.")

        # Create a single string with all inputs separated by newlines.
        input_string = "\n".join(map(str, inputs))
        temp_input_filename = "input.tmp"

        try:
            # Step 1: Write the input string to a temporary file using a "here document".
            # This is the most reliable way to handle multi-line input in a shell,
            # as it avoids complex quoting issues. Using a quoted delimiter 'EOT'
            # prevents the shell from trying to interpret the content.
            write_command = f"""
cat <<'EOT' > {temp_input_filename}
{input_string}
EOT
"""
            self.executor.run_command(write_command)

            # Step 2: Execute the student's program, redirecting the temp file to its stdin.
            full_command = f"{start_command} < {temp_input_filename}"
            exit_code, stdout, stderr = self.executor.run_command(full_command)

            if exit_code != 0:
                return TestResult(self.name, 0, f"The program exited with an error. Stderr: {stderr}")

            actual_output = stdout.strip()
            if actual_output == expected_output.strip():
                score = 100
                report = "Success! The program produced the correct output for the given inputs."
            else:
                score = 0
                report = f"Output did not match. Expected: '{expected_output.strip()}', but the program returned: '{actual_output}'"

            return TestResult(self.name, score, report)

        finally:
            # Step 3: Always clean up the temporary file.
            self.executor.run_command(f"rm {temp_input_filename}")


# ===============================================================
# endregion
# ===============================================================

class InputOutputTemplate(Template):
    """
    A template for command-line I/O assignments. It uses the SandboxExecutor
    to securely run student programs and validate their console output.
    """

    @property
    def template_name(self):
        return "Input/Output"

    @property
    def template_description(self):
        return "A template for grading assignments based on command-line input and output."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return False

    @property
    def requires_execution_helper(self) -> bool:
        return True

    @property
    def execution_helper(self):
        return self.executor

    def __init__(self, clean=False):
        
        if not clean:
            # Prepare the environment by running setup commands
            self.executor = SandboxExecutor.start()
            self._setup_environment()
        else:
            self.executor = None
        self.tests = {
            "expect_output": ExpectOutputTest(self.executor),
        }

    def _setup_environment(self):
        """Runs any initial setup commands, like compilation or dependency installation."""
        print("--- Setting up Input/Output environment ---")
        install_command = self.executor.config.get("commands", {}).get("install_dependencies")
        if install_command:
            exit_code, _, stderr = self.executor.run_command(install_command)
            if exit_code != 0:
                raise RuntimeError(f"Failed to run setup command '{install_command}': {stderr}")
        print("--- Environment setup complete ---")

    def stop(self):
        """Stops the sandbox executor."""
        if self.executor:
            self.executor.stop()

    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function


if __name__ == "__main__":
    import sys
    import os

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from connectors.models.autograder_request import AutograderRequest
    from connectors.models.assignment_config import AssignmentConfig
    from autograder.context import request_context


    def create_mock_submission():
        """Creates an in-memory file for a simple Python calculator."""
        calculator_py = """
import sys

def main():
    try:
        # Using sys.stdin.readline() is more robust for non-interactive scripts
        operation = sys.stdin.readline().strip()
        num1 = float(sys.stdin.readline().strip())
        num2 = float(sys.stdin.readline().strip())

        if operation == "sum":
            print(num1 + num2)
        elif operation == "subtract":
            print(num1 - num2)
        else:
            print("Unknown operation")
    except (ValueError, IndexError):
        print("Invalid input")

if __name__ == "__main__":
    main()
"""
        return {"calculator.py": calculator_py}


    def create_mock_configs():
        """Creates the mock setup and criteria configurations."""
        setup_config = {
            "runtime_image": "python:3.11-slim",
            "start_command": "python calculator.py"
        }
        criteria_config = {
            "base": {
                "subjects": {
                    "calculation_tests": {
                        "weight": 100,
                        "tests": [
                            {"name": "expect_output", "calls": [[["sum", 2, 2], "4.0"]]},
                            {"name": "expect_output", "calls": [[["subtract", 10, 5], "5.0"]]}
                        ]
                    }
                }
            }
        }
        return setup_config, criteria_config


    # --- Main Simulation Logic ---
    print("--- 1. Setting up mock environment ---")
    submission_files = create_mock_submission()
    setup_config, criteria_config = create_mock_configs()

    assignment_config = AssignmentConfig(criteria=criteria_config, feedback=None, setup=setup_config)
    autograder_request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="MockStudent"
    )
    request_context.set_request(autograder_request)

    template = None
    try:
        print("\n--- 2. Initializing Input/Output Template ---")
        template = InputOutputTemplate()

        print("\n--- 3. Running Tests ---")

        # Test 1: Sum (Will pass)
        test_func = template.get_test("expect_output")
        sum_result = test_func.execute(["sum", 2, 2], "4.0")
        print("\n[Sum Test Result]")
        print(f"  Score: {sum_result.score}")
        print(f"  Report: {sum_result.report}")

        # Test 2: Sum (Will fail)
        test_func = template.get_test("expect_output")
        sum_result = test_func.execute(["sum", 2, 2], "3.0")
        print("\n[Sum Test Result]")
        print(f"  Score: {sum_result.score}")
        print(f"  Report: {sum_result.report}")

        # Test 2: Subtract
        subtract_result = test_func.execute(["subtract", 10, 5], "5.0")
        print("\n[Subtract Test Result]")
        print(f"  Score: {subtract_result.score}")
        print(f"  Report: {subtract_result.report}")

    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if template:
            print("\n--- 4. Cleaning up sandbox environment ---")
            template.stop()


