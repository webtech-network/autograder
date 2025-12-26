from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.criteria_tree import TestCategory, Subject, Test


class CriteriaTreeProcesser(ABC):
    @abstractmethod
    def process_subject(self, subject: "Subject") -> Any:
        pass

    @abstractmethod
    def process_test(self, test: "Test") -> Any:
        pass

    @abstractmethod
    def process_category(self, category: "TestCategory") -> Any:
        pass
