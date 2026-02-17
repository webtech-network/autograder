from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName

class ExporterStep(Step):
    """
    Step that exports the final grading result to an external system (e.g., Upstash).
    """

    def __init__(self, exporter_service):
        self._exporter_service = exporter_service

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """
        Export the final grading result to an external system.
        Args:
            input: PipelineExecution containing the grading result from the GRADE step
        Returns:
            PipelineExecution with an added StepResult indicating success or failure of the export operation
        """
        try:
            # Extract username and score from input
            username = input.submission.username
            score = input.get_step_result(StepName.GRADE).data.final_score

            self._exporter_service.set_score(username, score)

            # Return success result
            return input.add_step_result(StepResult(
                step=StepName.EXPORTER,
                data=None,
                status=StepStatus.SUCCESS
            ))
        except Exception as e:
            # Return failure result
            return input.add_step_result(StepResult(
                step=StepName.EXPORTER,
                data=None,
                status=StepStatus.FAIL,
                error=str(e),
            ))
