import asyncio
import os
import json
from typing import List, Dict, Any

from autograder.core.test_engine.engine_port import EnginePort


class PytestAdapter(EnginePort):
    """
    Adapter for running pytest tests and normalizing their output asynchronously.
    """

    TEST_FILES = ["test_base.py", "test_bonus.py", "test_penalty.py"]

    # Pathing logic seems correct based on your file tree, so it remains unchanged.
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'validation')
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, '__tests__', 'results')
    SUBMISSION_DIR = os.path.join(REQUEST_BUCKET_DIR, 'submission')
    async def _install_dependencies(self):
        """
        Installs pytest and pytest-json-report asynchronously if not already installed.
        """
        print("Checking and installing pytest dependencies...")
        try:
            # Check if pytest is installed using an async subprocess
            proc_pytest = await asyncio.create_subprocess_exec(
                "pytest", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_pytest.wait()
            if proc_pytest.returncode != 0:
                raise FileNotFoundError
            print("pytest is already installed.")
        except FileNotFoundError:
            print("pytest not found. Installing pytest...")
            installer_proc = await asyncio.create_subprocess_exec("pip", "install", "pytest", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await installer_proc.wait()
            print("pytest installed successfully.")

        try:
            # Check for pytest-json-report
            proc_report = await asyncio.create_subprocess_exec(
                "pytest", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc_report.communicate()
            if "--json-report" not in stdout.decode():
                raise FileNotFoundError
            print("pytest-json-report is already installed.")
        except FileNotFoundError:
            print("pytest-json-report not found. Installing...")
            installer_proc = await asyncio.create_subprocess_exec("pip", "install", "pytest-json-report", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await installer_proc.wait()
            print("pytest-json-report installed successfully.")

    async def run_tests(self) -> List[str]:
        """
        Runs pytest asynchronously for base, bonus, and penalty test files.
        Generates JSON reports for each and returns their paths.
        """
        await self._install_dependencies()
        os.makedirs(self.RESULTS_DIR, exist_ok=True)
        report_paths = []

        for test_file_name in self.TEST_FILES:
            test_file_path = os.path.join(self.VALIDATION_DIR, "__tests__", test_file_name)
            if not os.path.exists(test_file_path):
                raise FileNotFoundError(f"Required test file not found: {test_file_path}")

            json_report_path = os.path.join(self.RESULTS_DIR, f"{os.path.splitext(test_file_name)[0]}.json")
            command = [
                "pytest",
                test_file_path,
                "--json-report",
                f"--json-report-file={json_report_path}"
            ]

            print(f"Running pytest for {test_file_name}...")
            # Use asyncio's non-blocking subprocess call
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for the subprocess to finish and capture output
            stdout, stderr = await process.communicate()

            if not os.path.exists(json_report_path) or os.path.getsize(json_report_path) == 0:
                print(f"Error: Pytest failed to generate a report for {test_file_name}.")
                if stdout:
                    print(f"STDOUT: {stdout.decode()}")
                if stderr:
                    print(f"STDERR: {stderr.decode()}")
                raise RuntimeError(f"Pytest execution failed for {test_file_name} and no report was generated.")

            print(f"Successfully ran {test_file_name}. Report saved to {json_report_path}")
            report_paths.append(json_report_path)

        return report_paths

    def normalize_output(self, report_paths: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Normalizes the pytest JSON report files into the autograder's standard format.
        (This method performs file I/O, which is blocking, but it's typically fast enough.
        For very high-concurrency scenarios, you could adapt it to use a library like `aiofiles`.)
        """
        normalized_results: Dict[str, List[Dict[str, str]]] = {"base": [], "bonus": [], "penalty": []}

        for report_path in report_paths:
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)

                file_name_without_ext = os.path.splitext(os.path.basename(report_path))[0]
                test_type = file_name_without_ext.replace('test_', '')

                if 'tests' in report_data:
                    for test in report_data['tests']:
                        test_name = test.get('nodeid', 'unknown_test').split("::")[-1]
                        outcome = test.get('outcome', 'skipped')
                        status = "passed" if outcome == "passed" else "failed"
                        message = ""
                        if outcome == "failed":
                            message = test.get('call', {}).get('longrepr', 'Test failed.')
                        elif outcome == "skipped":
                            message = "Test was skipped."

                        normalized_test = {
                            "test": test_name, "status": status, "message": message, "subject": test_type
                        }
                        if test_type in normalized_results:
                            normalized_results[test_type].append(normalized_test)

            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warning: Could not process report file {report_path}. Error: {e}")
            finally:
                if os.path.exists(report_path):
                    os.remove(report_path)

        # Save normalized results
        for test_type, results_list in normalized_results.items():
            output_file_path = os.path.join(self.RESULTS_DIR, f"test_{test_type}_results.json")
            with open(output_file_path, 'w') as outfile:
                json.dump(results_list, outfile, indent=2)
            print(f"Saved normalized results for '{test_type}' to {output_file_path}")

        return normalized_results


async def main():
    """ Example usage for the async adapter """
    adapter = PytestAdapter()
    try:
        report_files = await adapter.run_tests()
        normalized_results = adapter.normalize_output(report_files)
        print("\n--- Normalized Results ---")
        print(json.dumps(normalized_results, indent=2))
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    adapter = PytestAdapter()
    adapter.setup()