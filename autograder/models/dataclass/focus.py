from dataclasses import dataclass
from typing import List, Optional

from autograder.models.contracts.outcome import TestOutcome


@dataclass(frozen=True)
class FocusedTest:
    """An assessed criterion and the points it cost on the final score."""
    test_result: TestOutcome
    diff_score: float


@dataclass(frozen=True)
class Focus:
    """Prioritized criteria by category (base, penalty, bonus)."""
    base: List[FocusedTest]
    penalty: Optional[List[FocusedTest]]
    bonus: Optional[List[FocusedTest]]
