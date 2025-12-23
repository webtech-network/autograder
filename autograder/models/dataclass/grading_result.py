from dataclasses import dataclass
from typing import Optional


@dataclass
class GradingResult:
    final_score: float
    status: str
    feedback: Optional[str] = None
    result_tree: 'ResultTree' = None
    # In case of error
    error: Optional[str] = None
    failed_at_step: Optional[str] = None
