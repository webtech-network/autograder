from abc import ABC, abstractmethod
from typing import Dict, List
from autograder.builder.models.criteria_tree import TestResult
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
    def parameter_description(self) -> Dict[str, str]:
        """A dictionary describing each parameter."""
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> TestResult:
        """The concrete implementation of the test logic."""
        pass