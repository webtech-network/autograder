import json
import logging
from typing import Annotated, Any

import requests
from pydantic import Field

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from autograder.models.execution import ServerSession
from autograder.models.evaluation_error import EvaluationError


def _server(evaluation: EvaluationInput) -> ServerSession:
    """The assessed-server session bound to API evaluators by their capability."""
    if evaluation.session is None:
        raise EvaluationError("SERVER_CAPABILITY_UNAVAILABLE", "This host cannot start and reach an assessed server.", "capability")
    return evaluation.session

# ===============================================================
# region: Concrete TestFunction Implementations for API Testing
# ===============================================================

class HealthCheckTest(TestFunction):
    """A simple test to check if an API endpoint is alive and returns a 200 OK status."""

    maximum_files = 0

    required_capabilities = ("http_network",)

    @property
    def name(self):
        return "health_check"

    @property
    def description(self):
        return t("api_testing.health_check.description")

    def execute(self, evaluation: EvaluationInput, *, endpoint: Annotated[str, Field(
            min_length=1, description=t("api_testing.health_check.params.endpoint"))]) -> TestResult:
        """Executes the health check test."""

        report = ""
        score = 0

        locale = evaluation.locale
        sandbox = _server(evaluation)
        try:
            response = sandbox.make_request("GET", endpoint)
            if response.status_code == 200:
                score = 100
                report = t("api_testing.health_check.report.success", locale=locale, endpoint=endpoint)
            else:
                report = t("api_testing.health_check.report.failure", locale=locale, endpoint=endpoint, code=response.status_code)
        except requests.RequestException as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not reach the assessed API.", "capability", True) from e
        except Exception as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not assess the API.", "capability", True) from e

        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )


class CheckResponseJsonTest(TestFunction):
    """Checks if an endpoint returns a JSON with a specific key-value pair."""

    maximum_files = 0

    required_capabilities = ("http_network",)

    @property
    def name(self):
        return "check_response_json"

    @property
    def description(self):
        return t("api_testing.check_response_json.description")

    def execute(self, evaluation: EvaluationInput, *,
                endpoint: Annotated[str, Field(min_length=1, description=t("api_testing.check_response_json.params.endpoint"))],
                expected_key: Annotated[str, Field(min_length=1, description=t("api_testing.check_response_json.params.expected_key"))],
                expected_value: Annotated[Any, Field(description=t("api_testing.check_response_json.params.expected_value"))] = None,
                ) -> TestResult:
        """Executes the JSON validation test."""

        report = ""
        score = 0

        locale = evaluation.locale
        sandbox = _server(evaluation)
        try:
            response = sandbox.make_request("GET", endpoint)
            if response.status_code != 200:
                return TestResult(self.name, 0, t("api_testing.check_response_json.report.request_failed", locale=locale, code=response.status_code))

            try:
                data = response.json()
                if not isinstance(data, dict):
                    return TestResult(self.name, 0, t("api_testing.check_response_json.report.invalid_json", locale=locale, endpoint=endpoint))
                if data.get(expected_key) == expected_value:
                    score = 100
                    report = t("api_testing.check_response_json.report.success", locale=locale, endpoint=endpoint, key=expected_key, value=expected_value)
                else:
                    report = t("api_testing.check_response_json.report.failure", locale=locale, endpoint=endpoint, key=expected_key, expected=expected_value, actual=data.get(expected_key))
            except json.JSONDecodeError:
                report = t("api_testing.check_response_json.report.invalid_json", locale=locale, endpoint=endpoint)

        except requests.RequestException as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not reach the assessed API.", "capability", True) from e
        except Exception as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not assess the API.", "capability", True) from e

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
    A template for API testing assignments. It uses the ExecutionSession to securely
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
