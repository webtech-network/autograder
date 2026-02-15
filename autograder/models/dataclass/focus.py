from dataclasses import dataclass
from typing import List, Optional

from autograder.models.result_tree import TestResultNode


@dataclass
class FocusedTest:
    test_result: TestResultNode
    diff_score: float


@dataclass
class Focus:
    base: List[FocusedTest]
    penalty: Optional[List[FocusedTest]]
    bonus: Optional[List[FocusedTest]]
