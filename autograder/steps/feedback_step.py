from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.models.dataclass.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.services.report.reporter_service import ReporterService


class FeedbackStep(Step):
    def __init__(self,
                 reporter_service: ReporterService,
                 feedback_config: dict):
        self._reporter_service = reporter_service
        self._feedback_config = feedback_config

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """Adds feedback to the grading result using the reporter service."""
        try:
            result_tree = input.get_step_result(StepName.GRADE).data
            feedback = self._reporter_service.generate_feedback(
                grading_result=result_tree,
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