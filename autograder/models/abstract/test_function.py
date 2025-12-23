from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from autograder.builder.models.criteria_tree import TestResult
from autograder.builder.models.param_description import ParamDescription


class TestFunction(ABC):
    """
    An abstract base class for a single, executable test function.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The machine-readable name of the test (e.g., 'has_tag')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A human-readable description of what the test does."""
        pass

    @property
    @abstractmethod
    def parameter_description(self) -> List[ParamDescription]:
        """A list of ParamDescription objects describing each parameter (excluding file content)."""
        pass

    @property
    def required_file(self) -> Optional[str]:
        """
        The type of file content this test expects (e.g., 'HTML', 'CSS', 'JavaScript', 'JSON').
        Return None if the test doesn't require file content.
        """
        return None

    @abstractmethod
    def execute(self, *args, **kwargs) -> TestResult:
        """The concrete implementation of the test logic."""
        pass