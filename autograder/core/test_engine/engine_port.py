import glob
import json
import os
import subprocess
import time  # Import the time module
from abc import ABC, abstractmethod


class EnginePort(ABC):
    """
    Abstract class for the Engine, which is responsible for running the tests
    and generating the standard test report output.
    """
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    # Define SUBMISSION_DIR, assuming it's a subdirectory of VALIDATION_DIR
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'validation')
    SUBMISSION_DIR = os.path.join(VALIDATION_DIR, 'submission')  # Assuming this path
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, 'tests', 'results')

    def __init__(self):
        """
        Initializes the engine and a list to hold background processes.
        """
        self.background_processes = []

    def setup(self):
        """
        Parses autograder-setup.json to perform pre-grading checks.
        Handles both blocking and background commands.
        """
        SETUP_FILE = os.path.join(self.REQUEST_BUCKET_DIR, 'autograder-setup.json')
        print(f"Looking for setup file at: {SETUP_FILE}")
        if not os.path.isfile(SETUP_FILE):
            print("📄 No setup file found. Skipping setup checks.")
            return 0

        with open(SETUP_FILE, 'r') as f:
            config = json.load(f)

        fatal_errors = []

        # 1. File Existence Checks (remains the same)
        print("🔬 Checking for required files...")
        file_patterns = config.get('file_checks', [])
        for pattern in file_patterns:
            # Use glob to handle wildcards like '*'
            # Corrected path to be inside submission directory
            if not glob.glob(os.path.join(self.SUBMISSION_DIR, pattern)):
                error_msg = f"Required file or directory not found: '{pattern}'"
                print(f"❌ {error_msg}")
                fatal_errors.append({"type": "file_check", "message": error_msg})

        # 2. Execute Setup Commands
        commands = config.get('commands', [])
        for item in commands:
            command = item.get('command')
            name = item.get('name', command)
            is_background = item.get('background', False)

            if not command:
                continue

            print(f"▶️ Running: '{name}'")
            try:
                if is_background:
                    # 🚀 Launch as a background process using Popen
                    proc = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.SUBMISSION_DIR
                    )
                    # Wait a moment for the server to either start successfully or fail
                    time.sleep(3)

                    # Check if the process has already terminated (i.e., failed to start)
                    if proc.poll() is not None:
                        # Process terminated, so it's an error
                        stdout, stderr = proc.communicate()
                        error_msg = f"Background command '{name}' failed to start."
                        print(f"❌ {error_msg}")
                        print(f"   Stderr: {stderr.strip()}")
                        fatal_errors.append(
                            {"type": "command_failure", "message": error_msg, "details": stderr.strip()})
                    else:
                        # Process is still running, which is the success case for a server
                        print(f"✅ Background process '{name}' started successfully.")
                        self.background_processes.append(proc)
                else:
                    # 🏃‍♂️ Run as a normal, blocking process
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=True,  # Let it raise an exception on failure
                        capture_output=True,
                        text=True,
                        cwd=self.SUBMISSION_DIR
                    )
                    print(f"   Stdout: {result.stdout.strip()}")

            except subprocess.CalledProcessError as e:
                # 🛑 This will catch failures from the blocking commands
                error_msg = f"Command '{name}' failed with exit code {e.returncode}."
                print(f"❌ {error_msg}")
                print(f"   Stderr: {e.stderr.strip()}")
                fatal_errors.append({"type": "command_failure", "message": error_msg, "details": e.stderr.strip()})
            except Exception as e:
                error_msg = f"An unexpected error occurred while running command '{name}'."
                print(f"❌ {error_msg}: {e}")
                fatal_errors.append({"type": "command_execution", "message": error_msg, "details": str(e)})

        # 3. Write report if errors were found (remains the same)
        if fatal_errors:
            print(f"🚨 {len(fatal_errors)} fatal error(s) found. Generating report.")
            os.makedirs(self.RESULTS_DIR, exist_ok=True)  # Ensure results dir exists
            with open(os.path.join(self.RESULTS_DIR, 'fatal_report.json'), 'w') as f:
                json.dump({"errors": fatal_errors}, f, indent=2)
            return 1
        else:
            print("✅ All setup checks passed successfully.")
            return 0

    def teardown(self):
        """
        Cleans up and terminates any running background processes.
        """
        if not self.background_processes:
            print("🧹 No background processes to terminate.")
            return

        print(f"🧹 Terminating {len(self.background_processes)} background process(es)...")
        for proc in self.background_processes:
            proc.terminate()  # Sends SIGTERM
            try:
                # Wait a bit to see if it terminates gracefully
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # If not, force kill it
                print(f"   Process {proc.pid} did not terminate gracefully, forcing kill.")
                proc.kill()  # Sends SIGKILL
        self.background_processes = []

    @abstractmethod
    def run_tests(self):
        pass

    @abstractmethod
    def normalize_output(self):
        pass