from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.dataclass.param_description import ParamDescription
from sandbox_manager.sandbox_container import SandboxContainer


class TestFunction(ABC):
    """
    An abstract base class for a single, executable test function.
    """

    #: Host capabilities needed beyond the template sandbox flag (see catalog.Capability).
    required_capabilities: Tuple[str, ...] = ()
    #: Known evaluator language constraints; None declares no specific restriction.
    supported_languages: Optional[List[str]] = None
    #: Optional catalog example; otherwise required fields are synthesized from config_schema.
    example_parameters: Optional[Dict[str, Any]] = None

    @property
    def config_schema(self) -> Optional[Type[BaseModel]]:
        """Optional Pydantic model to validate test parameters during tree building."""
        from autograder.models.contracts.parameter_contract import signature_contract
        return signature_contract(self)

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the test (e.g., 'has_tag')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the test does."""

    @property
    @abstractmethod
    def parameter_description(self) -> List[ParamDescription]:
        """A list of ParamDescription objects describing each parameter (excluding file content)."""

    @property
    def required_file_type(self) -> Optional[str]:
        """
        The type of file content this test expects (e.g., 'HTML', 'CSS', 'JavaScript', 'JSON').
        Return None if the test doesn't require file content.
        """
        return None

    @abstractmethod
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """The concrete implementation of the test logic."""
