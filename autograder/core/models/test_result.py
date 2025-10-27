from pydantic import BaseModel, Field
from typing import Dict, Any

class TestResult(BaseModel):
    """Stores the outcome of a single test execution from the test library."""

    test_name: str
    score: int
    report: str
    subject_name: str = ""
    paremeters: Dict[str, Any] = Field(default_factory=dict)

    def get_result(self, *args, **kwargs) :
        return [self]

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "score": self.score,
            "subject_name": self.subject_name,
            "report": self.report,
            "parameters": self.parameters
        }

    def __repr__(self):
        return f"TestResult(subject='{self.subject_name}', name='{self.test_name}', score={self.score})"
