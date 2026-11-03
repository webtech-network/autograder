from typing import Mapping

from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import ResultTree, RootResultNode
from .criteria_grader import SubmissionGrader


class GraderService:
    """Aggregate ID-keyed assessed results over a compiled criteria tree."""

    def grade_from_tree(self, criteria_tree: CriteriaTree, results: Mapping[str, TestResult]) -> ResultTree:
        """Build the weighted result tree; evaluators already ran in ``assess_criteria``."""
        grader = SubmissionGrader(results)
        root = RootResultNode(name="root", base=grader.process_category(criteria_tree.base))
        if criteria_tree.bonus:
            root.bonus = grader.process_category(criteria_tree.bonus)
        if criteria_tree.penalty:
            root.penalty = grader.process_category(criteria_tree.penalty)
        return ResultTree(root)
