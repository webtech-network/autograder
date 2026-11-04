from dataclasses import dataclass
from typing import Optional, Tuple

from autograder.models.contracts.outcome import TestOutcome


@dataclass(frozen=True)
class FocusedTest:
    """An assessed criterion and the points it cost on the final score."""
    test_result: TestOutcome
    diff_score: float


@dataclass(frozen=True)
class Focus:
    """Criteria per category (base, penalty, bonus), most points lost first."""
    base: Tuple[FocusedTest, ...]
    penalty: Optional[Tuple[FocusedTest, ...]]
    bonus: Optional[Tuple[FocusedTest, ...]]
