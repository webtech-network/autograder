from typing import Any

import requests
import json
import logging
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        return t("api_testing.health_check.description")

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("endpoint", t("api_testing.health_check.params.endpoint"), "string")
        ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute(self, files , sandbox: SandboxContainer, endpoint: str = "", **kwargs) -> TestResult:
        """Executes the health check test."""

        report = ""
        score = 0

        locale = kwargs.get("locale")
        try:
            response = sandbox.make_request("GET", endpoint)
            if response.status_code == 200:
                score = 100
                report = t("api_testing.health_check.report.success", locale=locale, endpoint=endpoint)
            else:
                report = t("api_testing.health_check.report.failure", locale=locale, endpoint=endpoint, code=response.status_code)
        except requests.RequestException as e:
            report = t("api_testing.health_check.report.request_failed", locale=locale, error=str(e))
        except Exception as e:
            report = t("api_testing.health_check.report.unexpected_error", locale=locale, error=str(e))

        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )


class CheckResponseJsonTest(TestFunction):
    """Checks if an endpoint returns a JSON with a specific key-value pair."""

    @property
    def name(self):
        return "check_response_json"

    @property
    def description(self):
        return t("api_testing.check_response_json.description")

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("endpoint", t("api_testing.check_response_json.params.endpoint"), "string"),
            ParamDescription("expected_key", t("api_testing.check_response_json.params.expected_key"), "string"),
            ParamDescription("expected_value", t("api_testing.check_response_json.params.expected_value"), "any")
        ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute(self, files, sandbox: SandboxContainer, endpoint: str = "", expected_key: str = "", expected_value: Any = None, **kwargs) -> TestResult:
        """Executes the JSON validation test."""

        report = ""
        score = 0

        locale = kwargs.get("locale")
        try:
            response = sandbox.make_request("GET", endpoint)
            if response.status_code != 200:
                return TestResult(self.name, 0, t("api_testing.check_response_json.report.request_failed", locale=locale, code=response.status_code))

            try:
                data = response.json()
                if data.get(expected_key) == expected_value:
                    score = 100
                    report = t("api_testing.check_response_json.report.success", locale=locale, endpoint=endpoint, key=expected_key, value=expected_value)
                else:
                    report = t("api_testing.check_response_json.report.failure", locale=locale, endpoint=endpoint, key=expected_key, expected=expected_value, actual=data.get(expected_key))
            except json.JSONDecodeError:
                report = t("api_testing.check_response_json.report.invalid_json", locale=locale, endpoint=endpoint)

        except requests.RequestException as e:
            report = t("api_testing.health_check.report.request_failed", locale=locale, error=str(e))
        except Exception as e:
            report = t("api_testing.health_check.report.unexpected_error", locale=locale, error=str(e))

        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )


# ===============================================================
# endregion
# ===============================================================

class ApiTestingTemplate(Template):
    """
    A template for API testing assignments. It uses the SandboxContainer to securely
    run and test student-submitted web servers.
    """

    @property
    def template_name(self):
        return t("api_testing.template.name")

    @property
    def template_description(self):
        return t("api_testing.template.description")

    @property
    def requires_sandbox(self) -> bool:
        return True

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "health_check": HealthCheckTest(),
            "check_response_json": CheckResponseJsonTest(),
        }


    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
