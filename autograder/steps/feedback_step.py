from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.models.dataclass.pipeline_execution import PipelineExecution
from autograder.services.report.reporter_service import ReporterService


class FeedbackStep(Step):
    def __init__(self,
                 reporter_service: ReporterService,
                 feedback_config: dict):
        self._reporter_service = reporter_service
        self._feedback_config = feedback_config

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """Adds feedback to the grading result using the reporter service."""
        feedback = self._reporter_service.generate_feedback()
        input.feedback = feedback
        return
