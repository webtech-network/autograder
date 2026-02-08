from dataclasses import dataclass

@dataclass
class GradeStepResult:
    """Result of a grading step, keeps the result tree and final score."""
    final_score: float
    result_tree: 'ResultTree'