import logging

from typing import Dict, Any, Optional
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.result_tree import ResultTree
from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.services.graders.criteria_tree import CriteriaTreeGrader


class GraderService:
    def __init__(self):
        self.logger = logging.getLogger("GraderService")
        self._criteria_service = CriteriaTreeService()

    def grade_from_tree(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str, Any],
        submission_id: Optional[str] = None,
    ) -> ResultTree:
        grader = CriteriaTreeGrader(submission_files)
        return grader.grade(criteria_tree, submission_id)
