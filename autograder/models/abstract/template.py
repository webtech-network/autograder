from abc import ABC, abstractmethod
from typing import Dict

from autograder.models.abstract.test_function import TestFunction


class Template(ABC):
    @property
    @abstractmethod
    def template_name(self) -> str:
        pass

    @property
    @abstractmethod
    def template_description(self) -> str:
        pass

    @property
    @abstractmethod
    def requires_sandbox(self) -> bool:
        pass

    @abstractmethod
    def get_test(self, name: str) -> TestFunction:
        pass

    def get_tests(self) -> Dict[str, TestFunction]:
        tests = getattr(self, "tests", None)
        if not isinstance(tests, dict):
            raise TypeError("Template must define a 'tests' dictionary.")
        return tests

    def validate_contract(self) -> None:
        tests = self.get_tests()
        for test_name, test_function in tests.items():
            if not isinstance(test_name, str):
                raise TypeError("Template tests keys must be strings.")
            if not isinstance(test_function, TestFunction):
                raise TypeError(
                    f"Template test '{test_name}' must be a TestFunction instance."
                )
