import logging

from autograder.models.dataclass.grade_step_result import GradeStepResult
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
from autograder.models.abstract.step import Step
from autograder.services.grader_service import GraderService

logger = logging.getLogger(__name__)


class GradeStep(Step):
    """
    Step that grades a submission using the CriteriaTree and the Template over the submission files.

    This step represents the main grading logic, where the CriteriaTree is executed against a submission
    generating a result tree with scores for each test, subject, category and overall final score.
    """

    def __init__(
        self    ):
        """
        Initialize the grade step.
        """
        self._grader_service = GraderService()

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Grade a submission based on the criteria tree and template.

        Args:
            pipeline_exec: PipelineExecution containing the built criteria tree and submission files generated from previous steps

        Returns:
            StepResult containing GradingResult with scores and result tree
        """
        try:
            logger.info("Grading submission (user=%s)", pipeline_exec.submission.username)

            # If submission is sandboxed, feed grading template with container ref
            template = pipeline_exec.get_step_result(StepName.LOAD_TEMPLATE).data

            # Check if PRE_FLIGHT step was executed (only if setup_config was provided)
            sandbox = None
            if pipeline_exec.has_step_result(StepName.PRE_FLIGHT):
                sandbox = pipeline_exec.get_step_result(StepName.PRE_FLIGHT).data

            if sandbox:
                self._grader_service.set_sandbox(sandbox)

            if not sandbox and template.requires_sandbox:
                raise RuntimeError("Grading template requires a sandbox environment, but no sandbox was created")

            # Set submission language for command resolution
            if pipeline_exec.submission.language:
                self._grader_service.set_submission_language(pipeline_exec.submission.language)

            criteria_tree = pipeline_exec.get_step_result(StepName.BUILD_TREE).data
            result_tree = self._grader_service.grade_from_tree(
                criteria_tree=criteria_tree,
                submission_files=pipeline_exec.submission.submission_files
            )

            # Create grading result
            final_score = result_tree.calculate_final_score()

            grading_result = GradeStepResult(
                final_score=final_score, result_tree=result_tree
            )

            logger.info(
                "Grading completed: user=%s, score=%.2f",
                pipeline_exec.submission.username,
                final_score,
            )

            return pipeline_exec.add_step_result(StepResult(
                step=StepName.GRADE,
                data=grading_result,
                status=StepStatus.SUCCESS,
                original_input=pipeline_exec
            ))

        except Exception as e:
            logger.error(
                "Grading failed: user=%s, error=%s",
                pipeline_exec.submission.username,
                str(e),
            )
            # Return error result
            return pipeline_exec.add_step_result(StepResult(
                step=StepName.GRADE,
                data=None,
                status=StepStatus.FAIL,
                error=str(e),
                original_input=pipeline_exec,
            ))
