from dataclasses import dataclass
from typing import Optional, Tuple

from autograder.models.contracts.outcome import TestOutcome


@dataclass(frozen=True)
class FocusedTest:
    """An assessed criterion, the points it cost and its signed effect on the final score.

    ``diff_score`` is the points it missed, ``(100 - score) * share``.
    ``points`` is ``criterion_points``: negative for points a base or penalty
    criterion lost, positive for points a bonus criterion earned.
    """
    test_result: TestOutcome
    diff_score: float
    points: float


@dataclass(frozen=True)
class Focus:
    """Criteria per category (base, penalty, bonus), most points lost first."""
    base: Tuple[FocusedTest, ...]
    penalty: Optional[Tuple[FocusedTest, ...]]
    bonus: Optional[Tuple[FocusedTest, ...]]
