from autograder.models.abstract.step import Step
from autograder.models.dataclass.focus import Focus 
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.services.report.reporter_service import ReporterService


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

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """Adds feedback to the grading result using the reporter service."""
        try:
            focused_tests: Focus = input.get_step_result(StepName.FOCUS).data
            feedback = self._reporter_service.generate_feedback(
                grading_result=focused_tests,
                feedback_config=self._feedback_config
            ) #TODO: Implement generate_feedback method @joaovitoralvarenga
            return input.add_step_result(feedback) #Assuming feedback is a StepResult
        except Exception as e:
            return input.add_step_result(
                StepResult(
                step=StepName.FEEDBACK,
                data=None,
                status=StepStatus.FAIL,
                error=f"Failed to generate feedback: {str(e)}")
            )
