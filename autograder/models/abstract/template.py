from abc import ABC, abstractmethod

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

    def get_tests(self):
        return self.tests

