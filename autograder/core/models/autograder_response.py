from typing import List, Optional

from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult
from autograder.core.models.result_tree import ResultNode

from pydantic import BaseModel, Field, ConfigDict


class AutograderResponse(BaseModel):
    """
    Represents the response from the autograder.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    
    status: str
    final_score: float = 0.0
    feedback: str = ""
    test_report: Optional[List[TestResult]] = Field(default=None)
    result_tree: Optional[ResultNode] = None

    def __repr__(self) -> str:
        feedback_size = len(self.feedback) if self.feedback else 0
        return f"AutograderResponse(status={self.status}, final_score={self.final_score}, feedback_size={feedback_size})"
