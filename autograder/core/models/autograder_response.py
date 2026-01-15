from typing import List, Optional

from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult

from pydantic import BaseModel, Field


class AutograderResponse(BaseModel):
    """
    Represents the response from the autograder.
    """
    status: str
    final_score: float = 0.0
    feedback: str = ""
    test_report: List[TestResult] = Field(default_factory=list)

    def __repr__(self) -> str:
        feedback_size = len(self.feedback) if self.feedback else 0
        return f"AutograderResponse(status={self.status}, final_score={self.final_score}, feedback_size={feedback_size})"
