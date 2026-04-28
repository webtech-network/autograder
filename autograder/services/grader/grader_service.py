import logging
from typing import Dict, Optional

from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import (
    ResultTree,
    RootResultNode,
)
from autograder.services.command_resolver import CommandResolver
from .criteria_grader import SubmissionGrader


class GraderService:
    """Service responsible for orchestrating the grading process using a configured criteria tree."""

    def __init__(self):
        self.logger = logging.getLogger("GraderService")
        self._command_resolver = CommandResolver()

    def grade_from_tree(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
        structural_analysis=None,
    ) -> ResultTree:
        """Traverse the generic built criteria tree to resolve inputs, grades and report to ResultTree."""
        grader = SubmissionGrader(
            submission_files=submission_files,
            command_resolver=self._command_resolver,
            sandbox=sandbox,
            submission_language=submission_language,
            locale=locale,
            pre_computed_results=pre_computed_results,
            structural_analysis=structural_analysis,
        )

        base_result = grader.process_category(criteria_tree.base)
        root = RootResultNode(name="root", base=base_result)

        if criteria_tree.bonus:
            root.bonus = grader.process_category(criteria_tree.bonus)

        if criteria_tree.penalty:
            root.penalty = grader.process_category(criteria_tree.penalty)

        return ResultTree(root)
