import logging

from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.focus_service import FocusService

logger = logging.getLogger(__name__)


class FocusStep(Step):
    """
    Step that gets the main subjects to be analyzed by the AI
    """

    def __init__(self, trim_service: FocusService) -> None:
        self.__focus_service = trim_service

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Trim the result tree to get the main points of failure
        Args:
            pipeline_exec: PipelineExecution containtin the grading result from the GRADE step
        Returns:
            PipelineExecution with an added StepResult indicating success or failure of the trimming step
        """

        try:
            logger.info("Identifying focus areas (external_user_id=%s)", pipeline_exec.submission.user_id)
            result_tree = pipeline_exec.get_result_tree()
            main_subjects = self.__focus_service.find(result_tree)
            logger.info(
                "Focus areas identified (external_user_id=%s)",
                pipeline_exec.submission.user_id,
            )

            return pipeline_exec.add_step_result(
                StepResult(
                    step=StepName.FOCUS,
                    data=main_subjects,
                    status=StepStatus.SUCCESS,
                )
            )
        except Exception as e:
            logger.error(
                "Focus step failed: external_user_id=%s, error=%s",
                pipeline_exec.submission.user_id,
                str(e),
            )
            return pipeline_exec.add_step_result(
                StepResult(
                    step=StepName.FOCUS, data=None, status=StepStatus.FAIL, error=str(e)
                )
            )
