import glob
import json
import os
import subprocess
from abc import ABC, abstractmethod



class EnginePort(ABC):
    """
    Abstract class for the Engine, which is responsible for running the tests
    and generating the standard test report output.
    """
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, 'tests', 'results')
    def setup(self):
        """
            Parses assignment-setup.json to perform pre-grading checks.
            Generates a fatal_report.json if any checks fail.
            """
        SETUP_FILE = os.path.join(self.REQUEST_BUCKET_DIR, 'autograder-setup.json')
        print(SETUP_FILE)
        if not os.path.isfile(SETUP_FILE):
            print("📄 No setup file found. Skipping fatal checks.")
            return 0  # No fatal errors, so return 0

        with open(SETUP_FILE, 'r') as f:
            config = json.load(f)

        fatal_errors = []

        # 1. Perform File Existence Checks
        print("🔬 Checking for required files...")
        file_patterns = config.get('file_checks', [])
        for pattern in file_patterns:
            # Use glob to handle wildcards like '*'
            if not glob.glob(os.path.join(self.SUBMISSION_DIR, pattern)):

                error_msg = f"Required file or directory not found: '{pattern}'"
                print(f"❌ {error_msg}")
                fatal_errors.append({"type": "file_check", "message": error_msg})

        # 2. Execute Setup Commands and Check for Failures
        commands = config.get('commands', [])
        for item in commands:
            command = item.get('command')
            print("Executing command: ", command)
            name = item.get('name', command)

            if not command:
                continue

            print(f"▶️ Running: '{name}'")
            try:
                # Note: Assumes commands are run from the 'submission' directory
                subprocess.run(
                    command,
                    shell=True,
                    check=False,  # 'check=True' raises an exception on non-zero exit codes
                    capture_output=True,
                    text=True,
                    cwd=self.SUBMISSION_DIR  # Run command inside the student's code
                )
            except subprocess.CalledProcessError as e:

                error_msg = f"Command '{name}' failed with exit code {e.returncode}."
                print(f"❌ {error_msg}")
                print(f"   Stderr: {e.stderr.strip()}")
                fatal_errors.append({"type": "command_failure", "message": error_msg, "details": e.stderr.strip()})
            except Exception as e:

                error_msg = f"An unexpected error occurred while running command '{name}'."
                print(f"❌ {error_msg}: {e}")
                fatal_errors.append({"type": "command_execution", "message": error_msg, "details": str(e)})

        # 3. Write the report and exit if errors were found
        if fatal_errors:

            print(f"🚨 {len(fatal_errors)} fatal error(s) found. Generating report.")
            with open(f"{self.RESULTS_DIR}/fatal_report.json",'w') as f:
                json.dump({"errors": fatal_errors}, f, indent=2)
            # Exit with a non-zero status code to halt the autograder
            return 1
        else:
            print("✅ All fatal checks passed successfully.")
            return 0

    @abstractmethod
    def run_tests(self):
        pass

    @abstractmethod
    def normalize_output(self):
        pass


if __name__ == "__main__":
    print("EnginePort is an abstract class and cannot be instantiated directly.")
    