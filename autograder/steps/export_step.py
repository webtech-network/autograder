import logging

from autograder.models.abstract.exporter import Exporter
from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName

logger = logging.getLogger(__name__)


class ExporterStep(Step):
    """
    Step that exports the final grading result to an external system
    via a pluggable Exporter implementation.
    """

    def __init__(self, exporter_service: Exporter):
        self._exporter_service = exporter_service

    @property
    def step_name(self) -> StepName:
        return StepName.EXPORTER

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Export the final grading result to an external system.
        Args:
            pipeline_exec: PipelineExecution containing the grading result from the GRADE step
        Returns:
            PipelineExecution with an added StepResult indicating success or failure of the export operation
        """
        external_user_id = pipeline_exec.submission.user_id
        score = pipeline_exec.get_grade_step_result().final_score

        logger.info("Exporting result: external_user_id=%s, score=%.2f", external_user_id, score)
        self._exporter_service.export_with_context(pipeline_exec)
        logger.info("Result exported successfully: external_user_id=%s", external_user_id)

        # Return success result
        return pipeline_exec.add_step_result(StepResult(
            step=StepName.EXPORTER,
            data=None,
            status=StepStatus.SUCCESS
        ))

