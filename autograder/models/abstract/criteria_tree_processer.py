from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.criteria_tree import CategoryNode, SubjectNode, TestNode


class CriteriaTreeProcesser(ABC):
    """
    Abstract base class for processing the criteria tree structure.
    """
    @abstractmethod
    def process_subject(self, subject: "SubjectNode") -> Any:
        """Process a subject node in the criteria tree."""

    @abstractmethod
    def process_test(self, test: "TestNode") -> Any:
        """Process a test node in the criteria tree."""

    @abstractmethod
    def process_category(self, category: "CategoryNode") -> Any:
        """Process a category node in the criteria tree."""
