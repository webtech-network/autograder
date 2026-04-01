import logging

from autograder.models.abstract.step import Step
from autograder.models.dataclass.focus import Focus 
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
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

    @property
    def step_name(self) -> StepName:
        return StepName.FEEDBACK

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Adds feedback to the grading result using the reporter service."""
        logger.info("Generating feedback (external_user_id=%s)", pipeline_exec.submission.user_id)
        focused_tests: Focus = pipeline_exec.get_focus()
        result_tree = pipeline_exec.get_result_tree()
        
        feedback_content = self._reporter_service.generate_feedback(
            grading_result=focused_tests,
            result_tree=result_tree,
            feedback_config=self._feedback_config,
            locale=pipeline_exec.locale
        )
        logger.info("Feedback generated (external_user_id=%s)", pipeline_exec.submission.user_id)
        return pipeline_exec.add_step_result(
            StepResult(
                step=StepName.FEEDBACK,
                data=feedback_content,
                status=StepStatus.SUCCESS,
            )
        )
