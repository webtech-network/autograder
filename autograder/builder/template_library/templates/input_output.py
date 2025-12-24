import time
import json
import uuid
import re
import logging
import base64  # Added for robust input handling

from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.builder.models.param_description import ParamDescription
from autograder.core.models.test_result import TestResult
from autograder.builder.execution_helpers.sandbox_executor import SandboxExecutor


# ===============================================================
# region: TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(TestFunction):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output using flexible matching strategies.
    """

    @property
    def name(self):
        return "expect_output"

    @property
    def description(self):
        return "Executes the student's program with provided inputs and validates the output using configurable matching rules (exact, substring, or regex)."

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("inputs", "List of strings to send to the program (stdin), one per line.",
                             "list of strings"),
            ParamDescription("expected_output", "The string or pattern expected in the stdout.", "string"),
            ParamDescription("match_mode", "Matching strategy: 'exact', 'substring', or 'regex'. Default: 'substring'",
                             "string"),
            ParamDescription("ignore_case", "If true, performs case-insensitive matching.", "boolean"),
            ParamDescription("normalize_whitespace",
                             "If true, collapses all whitespace (newlines, tabs) to single spaces before matching.",
                             "boolean")
        ]

    def __init__(self, executor: SandboxExecutor):
        self.executor = executor
        self.logger = logging.getLogger(__name__)

    def execute(self, inputs: list, expected_output: str, match_mode: str = "substring", ignore_case: bool = False,
                normalize_whitespace: bool = True) -> TestResult:
        """
        Constructs and runs the command using unique temporary files for robustness,
        then validates the output according to the specified matching mode.
        """
        start_command = self.executor.config.get("start_command")
        if not start_command:
            raise ValueError("A 'start_command' must be defined in setup.json for this template.")

        # Generate a unique filename for input to avoid collisions
        temp_input_filename = f"input_{uuid.uuid4().hex}.tmp"

        # Prepare input content
        input_string = "\n".join(map(str, inputs))

        # Encode to base64 to avoid shell escaping issues with quotes/special chars
        # This ensures inputs like "It's a test" don't break the shell command wrapper
        input_b64 = base64.b64encode(input_string.encode('utf-8')).decode('utf-8')

        try:
            # Step 1: Write inputs to a temp file using base64 decoding
            # This is safer than heredocs because it avoids all shell character conflicts
            write_command = f"echo '{input_b64}' | base64 -d > {temp_input_filename}"
            self.executor.run_command(write_command)

            # Step 2: Execute the program with input redirection
            # We don't use a timeout here directly as SandboxExecutor/Docker usually handles generic timeouts,
            # but individual command timeouts could be added to SandboxExecutor in the future.
            full_command = f"{start_command} < {temp_input_filename}"
            exit_code, stdout, stderr = self.executor.run_command(full_command)

            # Step 3: Process Output
            actual_output = stdout if stdout else ""

            # If the program crashed, fail immediately but include stderr
            if exit_code != 0:
                return TestResult(
                    test_name=self.name,
                    score=0,
                    report=f"❌ Program execution failed (Exit Code: {exit_code}).\n\nSTDERR:\n{stderr}\n\nSTDOUT:\n{actual_output}"
                )

            # Step 4: Normalize and Match
            if ignore_case:
                actual_output = actual_output.lower()
                expected_output = expected_output.lower()

            if normalize_whitespace:
                # Collapse all whitespace sequences to a single space and strip edges
                actual_output = " ".join(actual_output.split())
                expected_output = " ".join(expected_output.split())
            else:
                # Just basic stripping
                actual_output = actual_output.strip()
                expected_output = expected_output.strip()

            # Matching Logic
            passed = False
            failure_details = ""

            if match_mode == "exact":
                passed = (actual_output == expected_output)
                if not passed:
                    failure_details = f"Expected exact match.\nExpected: '{expected_output}'\nActual:   '{actual_output}'"

            elif match_mode == "substring" or match_mode == "contains":
                passed = (expected_output in actual_output)
                if not passed:
                    failure_details = f"Expected output to contain substring.\nMissing: '{expected_output}'\nActual output: '{actual_output}'"

            elif match_mode == "regex":
                try:
                    passed = re.search(expected_output, actual_output) is not None
                    if not passed:
                        failure_details = f"Regex pattern not found.\nPattern: '{expected_output}'\nActual output: '{actual_output}'"
                except re.error as e:
                    return TestResult(self.name, 0, f"Invalid Regex Pattern provided in criteria: {e}")

            else:
                return TestResult(self.name, 0,
                                  f"Invalid match_mode: '{match_mode}'. Use 'exact', 'substring', or 'regex'.")

            # Step 5: Return Result
            if passed:
                return TestResult(
                    test_name=self.name,
                    score=100,
                    report="✅ Correct output generated."
                )
            else:
                return TestResult(
                    test_name=self.name,
                    score=0,
                    report=f"❌ Output mismatch.\n{failure_details}"
                )

        except Exception as e:
            self.logger.error(f"Error executing ExpectOutputTest: {e}")
            return TestResult(self.name, 0, f"An unexpected error occurred during testing: {str(e)}")

        finally:
            # Clean up the unique temp file
            self.executor.run_command(f"rm -f {temp_input_filename}")


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
        return "A robust template for grading command-line interfaces (CLI) based on input/output sequences."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return True

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