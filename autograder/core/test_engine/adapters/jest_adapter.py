import asyncio
import json
import os
import pathlib  # Added for robust path handling
from time import sleep
from typing import List, Dict, Any

from autograder.core.test_engine.engine_port import EnginePort


class JestAdapter(EnginePort):
    """
    JestAdapter is the adapter for the Jest test framework.
    It implements the EnginePort interface to run tests and normalize output asynchronously.
    """

    TEST_FILES = ["test_base.js", "test_bonus.js", "test_penalty.js"]

    # Pathing logic from the PytestAdapter for consistency.
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'validation')
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, '__tests__', 'results')
    SUBMISSION_DIR = os.path.join(REQUEST_BUCKET_DIR, 'submission')

    async def _check_dependencies(self):
        """
        Checks if npx is available, as it's used to run Jest.
        """
        print("Checking for Node.js environment (npx)...")
        try:
            # Use asyncio's subprocess to check for npx
            proc = await asyncio.create_subprocess_exec(
                "npx", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_message = stderr.decode() if stderr else "Process returned non-zero exit code."
                raise RuntimeError(f"npx version check failed: {error_message}")

            print(f"npx is available. Version: {stdout.decode().strip()}")

        except FileNotFoundError:
            raise RuntimeError(
                "`npx` command not found. Please ensure Node.js and npm are installed and accessible in the system's PATH.")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while checking for npx: {e}")

    async def run_tests(self) -> List[str]:
        """
        Run the tests using Jest.
        This method executes Jest tests for each specified test file, generates a JSON report,
        and returns the paths to these reports.
        """
        await self._check_dependencies()
        os.makedirs(self.RESULTS_DIR, exist_ok=True)
        report_paths = []

        for test_file_name in self.TEST_FILES:
            test_file_path = os.path.join(self.VALIDATION_DIR, "__tests__", test_file_name)

            if not os.path.exists(test_file_path):
                print(f"Warning: Test file not found, skipping: {test_file_path}")
                continue

            json_report_path = os.path.join(self.RESULTS_DIR, f"{os.path.splitext(test_file_name)[0]}_raw.json")
            command = [
                "npx", "jest", test_file_path, "--json", f"--outputFile={json_report_path}"
            ]

            print(f"Running Jest for {test_file_name}...")
            # Run the command from the validation directory to resolve local dependencies.
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.VALIDATION_DIR
            )

            stdout, stderr = await process.communicate()

            # Jest normally exits with code 1 if tests fail. This is not an execution error.
            # The real indicator of a problem is a missing report file.
            if not os.path.exists(json_report_path) or os.path.getsize(json_report_path) == 0:
                print(f"Error: Jest failed to generate a report for {test_file_name}.")
                if stdout:
                    print(f"STDOUT: {stdout.decode()}")
                if stderr:
                    print(f"STDERR: {stderr.decode()}")
                raise RuntimeError(f"Jest execution failed for {test_file_name}, no report was generated.")

            print(f"Successfully ran {test_file_name}. Report saved to {json_report_path}")
            report_paths.append(json_report_path)

        return report_paths

    def _parse_suite_failure_message(self, raw_message: str) -> str:
        """Helper to extract the core error from a failed test suite message."""
        if not raw_message:
            return "Test suite failed to run without a specific message."

        lines = raw_message.strip().split('\n')
        # Find the first meaningful error line, skipping Jest's boilerplate
        for line in lines:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith('●'):
                return clean_line

        return lines[0].strip()  # Fallback to the first line

    def normalize_output(self, report_paths: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Normalize the output from Jest tests.
        This method reads the raw JSON reports, transforms them into the standardized
        autograder format, and handles both individual test results and suite-level failures.
        """
        print("Normalizing Jest test results...")
        normalized_results: Dict[str, List[Dict[str, Any]]] = {"base": [], "bonus": [], "penalty": []}

        for report_path in report_paths:
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        print(f"Warning: Report file {report_path} is empty. Skipping.")
                        continue
                    report_data = json.loads(content)

                file_name_base = os.path.splitext(os.path.basename(report_path))[0]
                test_type = file_name_base.replace('test_', '').replace('_raw', '')

                if test_type not in normalized_results:
                    print(f"Warning: Unexpected test type '{test_type}' found. Skipping.")
                    continue

                for suite in report_data.get('testResults', []):
                    # SCENARIO 1: The entire test suite failed to run (e.g., syntax error)
                    if suite.get("status") == "failed" and not suite.get("assertionResults"):
                        normalized_test = {
                            "test": pathlib.Path(suite.get("name", "unknown_suite")).stem,
                            "status": "failed",
                            "message": self._parse_suite_failure_message(suite.get("message", "")),
                            "subject": test_type  # Subject is the category (base, bonus, etc.)
                        }
                        normalized_results[test_type].append(normalized_test)
                        continue

                    # SCENARIO 2: The suite ran, so process individual test results
                    for test in suite.get('assertionResults', []):
                        status = test.get('status', 'unknown')
                        message = ""

                        if status == 'failed':
                            message = "\n".join(
                                test.get('failureMessages', ['Test failed without a specific message.']))
                        elif status == 'passed':
                            # For passed tests, the message is the test's own title for clarity
                            message = test.get('title', 'Test passed.')

                        # Use the innermost 'describe' block as the subject for context,
                        # otherwise fall back to the test type (base, bonus, penalty).
                        subject = test_type
                        if test.get('ancestorTitles'):
                            subject = test['ancestorTitles'][-1].strip()

                        normalized_test = {
                            "test": test.get('title', 'Unknown Test'),
                            "status": status,
                            "message": message,
                            "subject": subject
                        }
                        normalized_results[test_type].append(normalized_test)

            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not process report file {report_path}. Error: {e}")
            finally:
                # Clean up the raw report file after processing
                if os.path.exists(report_path):
                    os.remove(report_path)

        # Save the normalized results into their own JSON files for clarity and debugging.
        for test_type, results_list in normalized_results.items():
            if results_list:
                output_file_path = os.path.join(self.RESULTS_DIR, f"test_{test_type}_results.json")
                with open(output_file_path, 'w', encoding='utf-8') as outfile:
                    json.dump(results_list, outfile, indent=2, ensure_ascii=False)

        return normalized_results