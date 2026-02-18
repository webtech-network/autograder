from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from autograder.models.result_tree import TestResultNode


@dataclass
class FocusedTest:
    test_result: TestResultNode
    diff_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert FocusedTest to dictionary for JSON serialization."""
        return {
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "diff_score": self.diff_score
        }


@dataclass
class Focus:
    base: List[FocusedTest]
    penalty: Optional[List[FocusedTest]]
    bonus: Optional[List[FocusedTest]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert Focus to dictionary for JSON serialization."""
        return {
            "base": [test.to_dict() for test in self.base] if self.base else [],
            "penalty": [test.to_dict() for test in self.penalty] if self.penalty else None,
            "bonus": [test.to_dict() for test in self.bonus] if self.bonus else None
        }

