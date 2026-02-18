from dataclasses import dataclass
from typing import Optional
from autograder.models.result_tree import ResultTree
from autograder.models.dataclass.focus import Focus


@dataclass
class GradingResult:
    final_score: float
    #status: str I'll evaluate if we keep this attribute or not
    feedback: Optional[str] = None
    result_tree: Optional['ResultTree'] = None
    focus: Optional['Focus'] = None  # Focus object organizing tests by impact

    # In case of error
    error: Optional[str] = None
    failed_at_step: Optional[str] = None
