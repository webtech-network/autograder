from dataclasses import dataclass, field
from typing import List

from autograder.models.dataclass.test_result import TestResult


@dataclass
class AutograderResponse:
    """
    Represents the response from the autograder.
    """
    status: str
    final_score: float = 0.0
    feedback: str = ""
    test_report: List[TestResult] = field(default_factory=list)

    def __repr__(self) -> str:
        feedback_size = len(self.feedback) if self.feedback else 0
        return f"AutograderResponse(status={self.status}, final_score={self.final_score}, feedback_size={feedback_size})"
