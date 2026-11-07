"""A template is a named collection of evaluators; identifiers are never restated."""
import pytest

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library import BUILTIN_TEMPLATES


class DummyTest(TestFunction):
    @property
    def name(self):
        return "dummy"

    @property
    def description(self):
        return "dummy"

    def execute(self, evaluation, *, x: int = 0):
        return TestResult(test_name=self.name, score=100.0, report="ok")


def test_builtin_templates_validate_contract():
    for template in BUILTIN_TEMPLATES.values():
        template.validate_contract()
        assert all(name == function.name for name, function in template.get_tests().items())


def test_evaluators_are_registered_under_their_own_name():
    evaluator = DummyTest()
    template = Template("Local", "Local evaluators", [evaluator])
    template.validate_contract()
    assert template.get_tests() == {"dummy": evaluator}
    assert template.get_test("dummy") is evaluator
    with pytest.raises(KeyError, match="not registered"):
        template.get_test("missing")


class PreOnb08Template(Template):
    """A subclass written the old way: a ``tests`` dict and no ``super().__init__``."""

    def __init__(self):  # pylint: disable=super-init-not-called
        self.template_name = "old"
        self.template_description = "old"
        self.tests = {"dummy": DummyTest()}


def test_template_contract_rejects_a_subclass_that_skips_the_base_constructor():
    with pytest.raises(TypeError, match=r"super\(\)\.__init__"):
        PreOnb08Template().validate_contract()


def test_template_contract_rejects_evaluators_that_are_not_a_tuple():
    template = Template("Local", "Local evaluators", [DummyTest()])
    template.evaluators = [DummyTest()]
    with pytest.raises(TypeError, match="Template\\(name, description, evaluators\\)"):
        template.validate_contract()


class OverriddenRegistry(Template):
    """Calls the base constructor but serves a registry that differs from ``evaluators``."""

    def __init__(self):
        super().__init__("Local", "Local evaluators", [DummyTest()])

    def get_tests(self):
        return {"renamed": self.evaluators[0]}


def test_template_contract_rejects_a_registry_that_differs_from_its_evaluators():
    with pytest.raises(TypeError, match="get_tests"):
        OverriddenRegistry().validate_contract()


def test_template_contract_rejects_non_test_function_values():
    with pytest.raises(TypeError, match="TestFunction"):
        Template("Local", "Local evaluators", [object()]).validate_contract()


def test_template_contract_rejects_duplicate_identifiers():
    with pytest.raises(ValueError, match="Duplicate evaluator identifier"):
        Template("Local", "Local evaluators", [DummyTest(), DummyTest()]).validate_contract()


def test_template_contract_rejects_empty_identifiers():
    class Unnamed(DummyTest):
        name = ""

    with pytest.raises(TypeError, match="nonempty"):
        Template("Local", "Local evaluators", [Unnamed()]).validate_contract()


def test_a_template_declares_no_requirements_of_its_own():
    """Capabilities live on evaluators only; templates carry no capability flag."""
    template = Template("Local", "Local evaluators", [DummyTest()])
    assert not hasattr(template, "requires_sandbox")
    assert vars(template).keys() == {"template_name", "template_description", "evaluators"}


def test_builtin_evaluator_identifiers_are_unique_across_templates():
    """A criterion ``type`` alone selects a built-in evaluator (format 2.0 lists no templates)."""
    identifiers = [name for template in BUILTIN_TEMPLATES.values() for name in template.get_tests()]
    assert len(identifiers) == len(set(identifiers))
