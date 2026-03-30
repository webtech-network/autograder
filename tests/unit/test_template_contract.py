import pytest

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library.api_testing import ApiTestingTemplate
from autograder.template_library.input_output import InputOutputTemplate
from autograder.template_library.web_dev.template import WebDevTemplate


class DummyTest(TestFunction):
    @property
    def name(self):
        return "dummy"

    @property
    def description(self):
        return "dummy"

    @property
    def parameter_description(self):
        return [ParamDescription("x", "x", "int")]

    def execute(self, *args, **kwargs):
        return TestResult(test_name=self.name, score=100.0, report="ok")


class InvalidTemplate(Template):
    @property
    def template_name(self) -> str:
        return "invalid"

    @property
    def template_description(self) -> str:
        return "invalid"

    @property
    def requires_sandbox(self) -> bool:
        return False

    def get_test(self, name: str):
        return DummyTest()


def test_builtin_templates_validate_contract():
    for template in [WebDevTemplate(), InputOutputTemplate(), ApiTestingTemplate()]:
        template.validate_contract()
        assert isinstance(template.get_tests(), dict)


def test_template_contract_rejects_missing_tests_dict():
    template = InvalidTemplate()
    with pytest.raises(TypeError, match="tests"):
        template.validate_contract()


def test_template_contract_rejects_non_test_function_values():
    template = InvalidTemplate()
    template.tests = {"bad": object()}
    with pytest.raises(TypeError, match="TestFunction"):
        template.validate_contract()

