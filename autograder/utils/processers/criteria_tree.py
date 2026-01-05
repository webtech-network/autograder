from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.criteria_tree import CategoryNode, SubjectNode, TestNode


class CriteriaTreeProcesser(ABC):
    @abstractmethod
    def process_subject(self, subject: "SubjectNode") -> Any:
        pass

    @abstractmethod
    def process_test(self, test: "TestNode") -> Any:
        pass

    @abstractmethod
    def process_category(self, category: "CategoryNode") -> Any:
        pass
