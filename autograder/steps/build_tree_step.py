from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.abstract.step import Step
from autograder.models.abstract.template import Template


class BuildTreeStep(Step):
    def __init__(self, criteria_json: dict):
        self._criteria_json = criteria_json
        self._criteria_tree_service = CriteriaTreeService

    def execute(self, input: Template) -> CriteriaTree:
        pass