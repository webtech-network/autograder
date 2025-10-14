from typing import List

from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult


class AutograderResponse:
    """
    Represents the response from the autograder.
    """

    def __init__(self,status, final_score: float = 0.0, feedback: str = "", test_report: List[TestResult] = None):
        self.status = status
        self.final_score = final_score
        self.feedback = feedback
        self.test_report = test_report
    def __repr__(self):
        return f"AutograderResponse(status={self.status}, final_score={self.final_score}, feedback_size={len(self.feedback)})"""