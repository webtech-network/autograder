import logging

from autograder.models.abstract.step import Step
from autograder.models.dataclass.focus import Focus 
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
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
            feedback = self._reporter_service.generate_feedback(
                grading_result=focused_tests,
                feedback_config=self._feedback_config
            ) #TODO: Implement generate_feedback method @joaovitoralvarenga
            logger.info("Feedback generated (external_user_id=%s)", pipeline_exec.submission.user_id)
            return pipeline_exec.add_step_result(feedback) #Assuming feedback is a StepResult
        except Exception as e:
            logger.error(
                "Feedback generation failed: external_user_id=%s, error=%s",
                pipeline_exec.submission.user_id,
                str(e),
            )
            return pipeline_exec.add_step_result(
                StepResult(
                step=StepName.FEEDBACK,
                data=None,
                status=StepStatus.FAIL,
                error=f"Failed to generate feedback: {str(e)}")
            )
