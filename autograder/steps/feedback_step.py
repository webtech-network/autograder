import logging

from autograder.models.abstract.step import Step
from autograder.models.dataclass.focus import Focus 
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepName, StepResult
from autograder.services.report.reporter_service import ReporterService

logger = logging.getLogger(__name__)


class FeedbackStep(Step):
    """
    Step that generates feedback for the grading result using the ReporterService.
    It takes the grading result from the GRADE step and produces feedback based on the provided feedback configuration.
    The feedback is a user-faced text that's highly configurable and can include explanations, suggestions and relevant learning resources.
    """
    def __init__(self,
                 reporter_service: ReporterService,
                 feedback_config: dict):
        self._reporter_service = reporter_service
        self._feedback_config = feedback_config

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Adds feedback to the grading result using the reporter service."""
        try:
            logger.info("Generating feedback (external_user_id=%s)", pipeline_exec.submission.user_id)
            focused_tests: Focus = pipeline_exec.get_step_result(StepName.FOCUS).data
            grade_result = pipeline_exec.get_step_result(StepName.GRADE).data
            
            feedback_content = self._reporter_service.generate_feedback(
                grading_result=focused_tests,
                result_tree=grade_result.result_tree,
                feedback_config=self._feedback_config
            )
            feedback = StepResult.success(
                step=StepName.FEEDBACK,
                data=feedback_content
            )
            logger.info("Feedback generated (external_user_id=%s)", pipeline_exec.submission.user_id)
            return pipeline_exec.add_step_result(feedback)
        except (ValueError, KeyError, AttributeError, TypeError, RuntimeError) as e:
            logger.error(
                "Feedback generation failed: external_user_id=%s, error=%s",
                pipeline_exec.submission.user_id,
                str(e),
            )
            return pipeline_exec.add_step_result(
                StepResult.fail(
                    step=StepName.FEEDBACK,
                    error=f"Failed to generate feedback: {str(e)}"
                )
            )
