from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class TestDelta:
    """
    Represents the score difference and status for a single test path
    between a baseline and a head grading execution.

    Attributes:
        path: Stable path string in "category/subject/.../test_name" format.
        status: One of "improved", "regressed", "unchanged", "introduced", "removed".
        baseline_score: Score in the baseline run, or None if introduced.
        head_score: Score in the head run, or None if removed.
        delta: head_score - baseline_score, or None if introduced/removed.
    """

    path: str
    status: str
    baseline_score: Optional[float] = None
    head_score: Optional[float] = None
    delta: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert TestDelta to a serializable dictionary."""
        return {
            "path": self.path,
            "status": self.status,
            "baseline_score": self.baseline_score,
            "head_score": self.head_score,
            "delta": self.delta,
        }


@dataclass
class ComparisonResult:
    """
    Structured outcome of comparing two ResultTree objects (baseline vs head).

    Attributes:
        score_delta: Change in final score (head.final_score - baseline.final_score).
        improved: True if score_delta > 0.
        test_deltas: List of per-test comparisons across all test paths.
    """

    score_delta: float
    improved: bool
    test_deltas: List[TestDelta] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert ComparisonResult to a serializable dictionary."""
        return {
            "score_delta": self.score_delta,
            "improved": self.improved,
            "test_deltas": [delta.to_dict() for delta in self.test_deltas],
        }
