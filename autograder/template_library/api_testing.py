from typing import Any

import requests
import json
import logging
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
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
        return "Verifica se um endpoint específico está em execução e retorna status code 200."

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("endpoint", "O endpoint a ser testado (ex: '/health').", "string")
        ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute(self, files , sandbox: SandboxContainer, endpoint: str = "", **kwargs) -> TestResult:
        """Executes the health check test."""

        report = ""
        score = 0

        try:
            response = sandbox.make_request("GET", endpoint)
            if response.status_code == 200:
                score = 100
                report = f"Success! Endpoint '{endpoint}' is alive and returned status code 200."
            else:
                report = f"Endpoint '{endpoint}' returned status code {response.status_code} instead of 200."
        except requests.RequestException as e:
            report = f"API request to the container failed: {e}"
        except Exception as e:
            report = f"An unexpected error occurred: {e}"

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
        return "Verifica se a resposta em JSON de um endpoint possui a chave e valor específicos."

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("endpoint", "O endpoint da API a ser testado (ex: '/api/data').", "string"),
            ParamDescription("expected_key", "A chave JSON que vai verificar a resposta.", "string"),
            ParamDescription("expected_value", "O valor esperado para a chave especificada.", "any")
        ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute(self, files, sandbox: SandboxContainer, endpoint: str = "", expected_key: str = "", expected_value: Any = None, **kwargs) -> TestResult:
        """Executes the JSON validation test."""

        report = ""
        score = 0

        try:
            response = sandbox.make_request("GET", endpoint)
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
            report = f"API request to the container failed: {e}"
        except Exception as e:
            report = f"An unexpected error occurred: {e}"

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
        return "API de Testes"

    @property
    def template_description(self):
        return "Um modelo para avaliar tarefas onde alunos criam uma API web."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return False

    @property
    def requires_sandbox(self) -> bool:
        return True

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "health_check": HealthCheckTest,
            "check_response_json": CheckResponseJsonTest,
        }


    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function


