from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class TestResult:
    """Stores the outcome of a single test execution from the test library."""

    test_name: str
    score: int
    report: str
    subject_name: str = ""
    parameters: Optional[Dict[str, Any]] = field(default_factory=dict)

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