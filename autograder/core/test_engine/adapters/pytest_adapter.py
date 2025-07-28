import subprocess
import os
import json
import shutil
from typing import List, Dict, Any

from autograder.core.test_engine.engine_port import EnginePort


# Assuming TestResult and Result are defined elsewhere if still needed for other parts of the core,
# but normalize_output will now return a different structure.
# from autograder.core.grading.models.result import TestResult, Result


class PytestAdapter(EnginePort):
    """
    Adapter for running pytest tests and normalizing their output.
    """

    TEST_FILES = ["test_base.py", "test_bonus.py", "test_penalty.py"]
    VALIDATION_DIR = os.path.join(os.getcwd(), 'autograder', 'validation')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, 'tests', 'results')

    def __init__(self):
        """
        Initializes the PytestAdapter.
        """
        pass

    def _install_dependencies(self):
        """
        Installs pytest and pytest-json-report if not already installed.
        """
        print("Checking and installing pytest dependencies...")
        try:
            # Check if pytest is installed
            subprocess.run(["pytest", "--version"], check=True, capture_output=True)
            print("pytest is already installed.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("pytest not found. Installing pytest...")
            subprocess.run(["pip", "install", "pytest"], check=True)
            print("pytest installed successfully.")

        try:
            # Check if pytest-json-report is installed
            subprocess.run(["pytest", "--help"], check=True, capture_output=True)
            # A simple check for '--json-report' in help output is a heuristic
            help_output = subprocess.run(["pytest", "--help"], capture_output=True, text=True, check=True).stdout
            if "--json-report" not in help_output:
                raise FileNotFoundError  # Simulate not found if option is missing
            print("pytest-json-report is already installed.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("pytest-json-report not found. Installing pytest-json-report...")
            subprocess.run(["pip", "install", "pytest-json-report"], check=True)
            print("pytest-json-report installed successfully.")
        print("Pytest dependencies check complete.")

    def run_tests(self) -> List[str]:
        """
        Runs pytest for base, bonus, and penalty test files.
        Generates JSON reports for each and returns their paths.

        Raises:
            FileNotFoundError: If any of the required test files are missing.
            subprocess.CalledProcessError: If pytest execution fails.

        Returns:
            List[str]: A list of paths to the generated JSON report files.
        """
        self._install_dependencies()

        # Ensure the results directory exists
        os.makedirs(self.RESULTS_DIR, exist_ok=True)

        report_paths = []

        for test_file_name in self.TEST_FILES:
            test_file_path = os.path.join(self.VALIDATION_DIR, f"tests/{test_file_name}")

            if not os.path.exists(test_file_path):
                raise FileNotFoundError(
                    f"Required test file not found: {test_file_path}. "
                    "Please ensure all base, bonus, and penalty test files are present."
                )

            json_report_path = os.path.join(self.RESULTS_DIR, f"{os.path.splitext(test_file_name)[0]}.json")

            print(f"Running pytest for {test_file_name}...")
            try:
                # Run pytest and generate JSON report
                # Removed check=True so that failing tests do not raise a CalledProcessError.
                # Pytest will still exit with a non-zero code for failures, but subprocess.run
                # will not raise an exception, allowing the report to be generated.
                command = [
                    "pytest",
                    test_file_path,
                    "--json-report",
                    f"--json-report-file={json_report_path}"
                ]
                result = subprocess.run(command, capture_output=True, text=True)

                # Check if the report file was actually created.
                # If pytest failed to generate the report (e.g., syntax error in test file),
                # then we should still raise an error.
                if not os.path.exists(json_report_path) or os.path.getsize(json_report_path) == 0:
                    print(f"Error: Pytest failed to generate a report for {test_file_name}.")
                    print(f"STDOUT: {result.stdout}")
                    print(f"STDERR: {result.stderr}")
                    raise RuntimeError(
                        f"Pytest execution failed for {test_file_name} and no report was generated. See logs above.")

                print(f"Successfully ran {test_file_name}. Report saved to {json_report_path}")
                report_paths.append(json_report_path)
            except Exception as e:
                print(f"An unexpected error occurred while running pytest for {test_file_name}: {e}")
                raise

        return report_paths

    def normalize_output(self, report_paths: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Normalizes the pytest JSON report files into the autograder's standard test report convention.
        Saves the normalized results as JSON files (e.g., test_base_results.json) and deletes
        the temporary pytest JSON report files after processing.

        Args:
            report_paths (List[str]): A list of paths to the pytest JSON report files.

        Returns:
            Dict[str, List[Dict[str, str]]]: A dictionary with keys 'base', 'bonus', 'penalty',
                                             each containing a list of test results in the
                                             autograder's standard format.
        """
        normalized_results: Dict[str, List[Dict[str, str]]] = {
            "base": [],
            "bonus": [],
            "penalty": []
        }

        for report_path in report_paths:
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)

                # Extract test type from the report file path (e.g., 'test_base', 'test_bonus')
                # This will be used as the 'subject' in the normalized output
                file_name_without_ext = os.path.splitext(os.path.basename(report_path))[0]
                test_type = file_name_without_ext.replace('test_', '')

                if 'tests' in report_data and isinstance(report_data['tests'], list):
                    for test in report_data['tests']:
                        test_name = test.get('nodeid', 'unknown_test').split("::")[-1]  # Extract test name from nodeid
                        outcome = test.get('outcome', 'skipped')  # passed, failed, skipped

                        # Determine status and message based on outcome
                        status = "passed" if outcome == "passed" else "failed"
                        message = ""
                        if outcome == "failed":
                            # Attempt to get error message from pytest report structure
                            longrepr = test.get('call', {}).get('longrepr')
                            if isinstance(longrepr, dict) and 'reprcrash' in longrepr:
                                message = longrepr['reprcrash'].get('message', 'Test failed.')
                            elif isinstance(longrepr, str):
                                message = longrepr
                            else:
                                message = "Test failed with no specific error message provided."
                        elif outcome == "skipped":
                            status = "skipped"
                            message = "Test was skipped."

                        # Create a dictionary conforming to the autograder's standard test report structure
                        normalized_test = {
                            "test": test_name,
                            "status": status,
                            "message": message,
                            "subject": test_type #TODO -> Add correct subject according to criteria.json
                        }

                        # Append to the correct category
                        if test_type in normalized_results:
                            normalized_results[test_type].append(normalized_test)
                        else:
                            print(f"Warning: Unknown test type '{test_type}' encountered. Skipping test: {test_name}")
                else:
                    print(f"Warning: 'tests' key not found or not a list in {report_path}. Skipping.")

            except FileNotFoundError:
                print(f"Warning: Report file not found during normalization: {report_path}")
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from file: {report_path}")
            except Exception as e:
                print(f"An unexpected error occurred while processing {report_path}: {e}")
            finally:
                # Delete the temporary Pytest JSON report file
                if os.path.exists(report_path):
                    os.remove(report_path)
                    print(f"Deleted temporary pytest report file: {report_path}")

        # After processing all pytest reports, save the normalized results to new JSON files
        for test_type, results_list in normalized_results.items():
            output_file_name = f"test_{test_type}_results.json"
            output_file_path = os.path.join(self.RESULTS_DIR, output_file_name)
            try:
                with open(output_file_path, 'w') as outfile:
                    json.dump(results_list, outfile, indent=2)
                print(f"Saved normalized results for '{test_type}' to {output_file_path}")
            except Exception as e:
                print(f"Error saving normalized results for '{test_type}' to {output_file_path}: {e}")

        # Clean up the results directory if empty after all operations
        if os.path.exists(self.RESULTS_DIR) and not os.listdir(self.RESULTS_DIR):
            try:
                os.rmdir(self.RESULTS_DIR)
                print(f"Deleted empty results directory: {self.RESULTS_DIR}")
            except OSError as e:
                print(f"Error deleting empty results directory {self.RESULTS_DIR}: {e}")

        return normalized_results


if __name__ == "__main__":
    # Example usage of the PytestAdapter
    adapter = PytestAdapter()
    try:
        print(adapter.VALIDATION_DIR)
        report_files = adapter.run_tests()
        normalized_results = adapter.normalize_output(report_files)
        print("Normalized Results:", json.dumps(normalized_results, indent=2))
    except Exception as e:
        print(f"An error occurred: {e}")
