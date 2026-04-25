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

    @property
    def step_name(self) -> StepName:
        return StepName.GRADE

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Grade a submission based on the criteria tree and template.

        Args:
            pipeline_exec: PipelineExecution containing the built criteria tree and submission files generated from previous steps

        Returns:
            StepResult containing GradingResult with scores and result tree
        """
        logger.info("Grading submission (external_user_id=%s)", pipeline_exec.submission.user_id)

        # If submission is sandboxed, feed grading template with container ref
        template = pipeline_exec.get_loaded_template()

        # Check if PRE_FLIGHT step was executed (only if setup_config was provided)
        sandbox = pipeline_exec.get_sandbox()

        if not sandbox and template.requires_sandbox:
            raise RuntimeError("Grading template requires a sandbox environment, but no sandbox was created")

        criteria_tree = pipeline_exec.get_built_criteria_tree()

        # Retrieve pre-computed AI results produced by AiBatchStep (if the step ran).
        pre_computed_results = None
        if pipeline_exec.has_step_result(StepName.AI_BATCH):
            pre_computed_results = pipeline_exec.get_step_result(StepName.AI_BATCH).data

        structural_analysis = pipeline_exec.get_structural_analysis_result()

        result_tree = self._grader_service.grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=pipeline_exec.submission.submission_files,
            sandbox=sandbox,
            submission_language=pipeline_exec.submission.language,
            locale=pipeline_exec.locale,
            pre_computed_results=pre_computed_results,
            structural_analysis=structural_analysis,
        )

        # Create grading result
        final_score = result_tree.calculate_final_score()

        grading_result = GradeStepResult(
            final_score=final_score, result_tree=result_tree
        )

        logger.info(
            "Grading completed: external_user_id=%s, score=%.2f",
            pipeline_exec.submission.user_id,
            final_score,
        )

        return pipeline_exec.add_step_result(StepResult(
            step=StepName.GRADE,
            data=grading_result,
            status=StepStatus.SUCCESS,
            original_input=pipeline_exec
        ))
