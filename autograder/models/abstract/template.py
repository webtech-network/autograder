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
    def requires_pre_executed_tree(self) -> bool: # TODO: remove pre_executed tree logic
        pass

    @property
    @abstractmethod
    def requires_sandbox(self) -> bool:
        pass


    @abstractmethod
    def get_test(self, name: str) -> TestFunction:
        pass

    @abstractmethod
    def stop(self):
        pass

    def get_tests(self):
        return self.tests

