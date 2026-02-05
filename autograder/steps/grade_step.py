
from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
from autograder.models.abstract.step import Step
from autograder.services.grader_service import GraderService


class GradeStep(Step):
    """
    Step that grades a submission using either a CriteriaTree or raw criteria configuration.

    This step intelligently determines which grading method to use:
    - If input is CriteriaTree: Use grade_from_tree (for multiple submissions)
    - If input is Template: Use grade_from_config (for single submission)
    """

    def __init__(
        self    ):
        """
        Initialize the grade step.

        Args:
            criteria_json: Raw criteria configuration (only needed for single submission mode)
            submission_files: Student submission files
        """
        self._grader_service = GraderService()

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """
        Grade a submission based on the input type.

        Args:
            _input: Either a CriteriaTree (multi-submission mode) or Template (single submission mode)

        Returns:
            StepResult containing GradingResult with scores and result tree
        """
        try:
            criteria_tree = input.get_step_result(StepName.BUILD_TREE).data
            result_tree = self._grader_service.grade_from_tree(
                criteria_tree=criteria_tree,
                submission_files=input.submission.submission_files
            )

            # Create grading result
            final_score = result_tree.calculate_final_score()

            grading_result = GradingResult(
                final_score=final_score, status="success", result_tree=result_tree
            )

            return input.add_step_result(StepResult(
                step=StepName.GRADE,
                data=grading_result,
                status=StepStatus.SUCCESS,
                original_input=input
            ))

        except Exception as e:
            # Return error result
            return input.add_step_result(StepResult(
                step="GradeStep",
                data=None,
                status=StepStatus.FAIL,
                error=str(e),
                original_input=input,
            ))
