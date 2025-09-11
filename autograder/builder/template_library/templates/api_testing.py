import time
import requests
import json

from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult
from autograder.builder.execution_helpers.sandbox_executor import SandboxExecutor


# ===============================================================
# region: Concrete TestFunction Implementations for API Testing
# ===============================================================

class HealthCheckTest(TestFunction):
    """A simple test to check if an API endpoint is alive and returns a 200 OK status."""

    @property
    def name(self):
        return "health_check"

    @property
    def description(self):
        return "Checks if a specific endpoint is running and returns a 200 OK status."

    @property
    def parameter_description(self):
        return {
            "endpoint": "The endpoint to test (e.g., '/health')."
        }

    def __init__(self, executor: SandboxExecutor):
        self.executor = executor

    def execute(self, endpoint: str) -> TestResult:
        """Executes the health check test."""

        url = f"http://localhost:{self.executor.HOST_PORT}{endpoint}"
        report = ""
        score = 0

        try:
            print(f"Making request to sandboxed API at: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                score = 100
                report = f"Success! The endpoint '{endpoint}' is running and returned a 200 OK status."
            else:
                score = 0
                report = f"The endpoint '{endpoint}' is running but returned a status code of {response.status_code}. Expected 200."

        except requests.ConnectionError:
            report = f"Connection failed. Could not connect to the API at '{url}'. Is the server running correctly?"
        except requests.Timeout:
            report = f"The request timed out. The API at '{url}' did not respond in time."
        except Exception as e:
            report = f"An unexpected error occurred: {e}"

        return TestResult(self.name, score, report)


class CheckResponseJsonTest(TestFunction):
    """Checks if an endpoint returns a JSON with a specific key-value pair."""

    @property
    def name(self):
        return "check_response_json"

    @property
    def description(self):
        return "Checks if an endpoint's JSON response contains a specific key and value."

    @property
    def parameter_description(self):
        return {
            "endpoint": "The API endpoint to test (e.g., '/api/data').",
            "expected_key": "The JSON key to check in the response.",
            "expected_value": "The expected value for the specified key."
        }

    def __init__(self, executor: SandboxExecutor):
        self.executor = executor

    def execute(self, endpoint: str, expected_key: str, expected_value: any) -> TestResult:
        """Executes the JSON validation test."""

        url = f"http://localhost:{self.executor.HOST_PORT}{endpoint}"
        report = ""
        score = 0

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return TestResult(self.name, 0, f"Request failed with status code {response.status_code}.")

            try:
                data = response.json()
                if data.get(expected_key) == expected_value:
                    score = 100
                    report = f"Success! Response from '{endpoint}' contained the expected key-value pair ('{expected_key}': '{expected_value}')."
                else:
                    report = f"JSON response from '{endpoint}' did not contain the expected value. Expected '{expected_value}' for key '{expected_key}', but got '{data.get(expected_key)}'."
            except json.JSONDecodeError:
                report = f"Response from '{endpoint}' was not valid JSON."

        except requests.RequestException as e:
            report = f"API request to '{url}' failed: {e}"
        except Exception as e:
            report = f"An unexpected error occurred: {e}"

        return TestResult(self.name, score, report)


# ===============================================================
# endregion
# ===============================================================

class ApiTestingTemplate(Template):
    """
    A template for API testing assignments. It uses the SandboxExecutor to securely
    run and test student-submitted web servers.
    """

    @property
    def template_name(self):
        return "API Testing"

    @property
    def template_description(self):
        return "A template for grading assignments where students create a web API."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return False

    @property
    def requires_execution_helper(self) -> bool:
        return True

    @property
    def execution_helper(self):
        return self.executor

    def __init__(self):
        self.executor = SandboxExecutor.start()

        # Prepare the environment by running setup commands
        self._setup_environment()

        self.tests = {
            "health_check": HealthCheckTest(self.executor),
            "check_response_json": CheckResponseJsonTest(self.executor),
        }

    def _setup_environment(self):
        """Runs initial setup commands like installing dependencies and starting the server."""
        print("--- Setting up API environment ---")

        # Install dependencies (e.g., npm install)
        install_command = self.executor.config.get("commands", {}).get("install_dependencies")
        if install_command:
            exit_code, _, _ = self.executor.run_command(install_command)
            if exit_code != 0:
                raise RuntimeError("Failed to install dependencies. Halting grading.")

        # Start the student's API server in the background
        start_command = self.executor.config.get("start_command")
        if not start_command:
            raise ValueError("A 'start_command' must be defined in setup.json for the API template.")

        self.executor.run_command(start_command, in_background=True)
        print("API server start command issued. Waiting for it to initialize...")
        time.sleep(5)  # Give the server a few seconds to start up
        print("--- Environment setup complete ---")

    def stop(self):
        """Stops the sandbox executor, which cleans up the container."""
        if self.executor:
            self.executor.stop()

    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
