from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.services.grader_service import GraderService


class GradeStep(Step):

    def __init__(self):
        self.submission_files = None # Injected at runtime
        self._grader_service = GraderService() # GraderService here

    def execute(self, input: CriteriaTree) -> GradingResult: # StepResult<GradingResult>
        """Generate a grading result based on the criteria tree execution over a submission"""
        pass

