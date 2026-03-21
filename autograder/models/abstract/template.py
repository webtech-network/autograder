from abc import ABC, abstractmethod
from typing import Dict

from autograder.models.abstract.test_function import TestFunction


class Template(ABC):
    """Abstract contract for all autograder templates."""

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

    @abstractmethod
    def get_test(self, name: str) -> TestFunction:
        """Return a test function instance by its registry name."""
        raise NotImplementedError

    def get_tests(self) -> Dict[str, TestFunction]:
        """Return the template test registry."""
        tests = getattr(self, "tests", None)
        if not isinstance(tests, dict):
            raise TypeError("Template must define a 'tests' dictionary.")
        return tests

    def validate_contract(self) -> None:
        """Validate template registry shape and value types."""
        tests = self.get_tests()
        for test_name, test_function in tests.items():
            if not isinstance(test_name, str):
                raise TypeError("Template tests keys must be strings.")
            if not isinstance(test_function, TestFunction):
                raise TypeError(
                    f"Template test '{test_name}' must be a TestFunction instance."
                )
