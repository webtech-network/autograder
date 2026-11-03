"""A trusted template: a named registry of evaluator instances."""
from abc import ABC, abstractmethod
from typing import Dict

from autograder.models.abstract.test_function import TestFunction


class Template(ABC):
    """Subclasses provide metadata and a ``tests`` dict ``{identifier: evaluator}``.

    Registry lookup is implemented here once; templates do not override it.
    """

    tests: Dict[str, TestFunction]

    @property
    @abstractmethod
    def template_name(self) -> str:
        """Return the human-readable template name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def template_description(self) -> str:
        """Return the template description shown to users."""
        raise NotImplementedError

    @property
    @abstractmethod
    def requires_sandbox(self) -> bool:
        """Declare whether template tests require sandbox execution."""
        raise NotImplementedError

    def get_tests(self) -> Dict[str, TestFunction]:
        """Return the template test registry."""
        tests = getattr(self, "tests", None)
        if not isinstance(tests, dict):
            raise TypeError("Template must define a 'tests' dictionary.")
        return tests

    def get_test(self, name: str) -> TestFunction:
        """Return a registered evaluator by its identifier."""
        try:
            return self.get_tests()[name]
        except KeyError:
            raise KeyError(f"Evaluator '{name}' is not registered in template '{self.template_name}'") from None

    def validate_contract(self) -> None:
        """Validate registry shape, identifiers and each evaluator's call shape."""
        from autograder.models.contracts.parameter_contract import check_invocation
        for test_name, test_function in self.get_tests().items():
            if not isinstance(test_name, str) or not test_name:
                raise TypeError("Template tests keys must be nonempty strings.")
            if not isinstance(test_function, TestFunction):
                raise TypeError(f"Template test '{test_name}' must be a TestFunction instance.")
            if test_function.name != test_name:
                raise ValueError("Evaluator registry key must match its explicit identifier")
            check_invocation(test_function)
