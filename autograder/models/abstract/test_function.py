from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.result_tree import TestResultNode
from autograder.models.dataclass.param_description import ParamDescription


class TestFunction(ABC):
    """
    An abstract base class for a single, executable test function.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the test (e.g., 'has_tag')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the test does."""
        pass

    @property
    @abstractmethod
    def parameter_description(self) -> List[ParamDescription]:
        """A list of ParamDescription objects describing each parameter (excluding file content)."""
        pass

    @property
    def required_file_type(self) -> Optional[str]:
        """
        The type of file content this test expects (e.g., 'HTML', 'CSS', 'JavaScript', 'JSON').
        Return None if the test doesn't require file content.
        """
        return None

    @abstractmethod
    def execute(self, files: Optional[List[SubmissionFile]] , *args, **kwargs) -> TestResult:
        """The concrete implementation of the test logic."""
        pass