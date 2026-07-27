import logging
from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName, StepCategory
from autograder.services.pre_flight_service import PreFlightService

logger = logging.getLogger(__name__)


class FileCheckStep(Step):
    """
    Step responsible for validating that all required files exist in the submission.
    This step runs before sandbox creation.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config

    @property
    def step_name(self) -> StepName:
        return StepName.FILE_CHECK

    @property
    def category(self) -> StepCategory:
        return StepCategory.SETUP

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        submission_language = pipeline_exec.submission.language
        pre_flight_service = PreFlightService(self._setup_config, submission_language, locale=pipeline_exec.locale)

        if not pre_flight_service.required_files:
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

        logger.info("Checking required files for submission (external_user_id=%s)", pipeline_exec.submission.user_id)
        files_ok = pre_flight_service.check_required_files(pipeline_exec.submission.submission_files)

        if not files_ok:
            error_msg = "\n".join(pre_flight_service.get_error_messages())
            logger.warning("Required files check failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=error_msg,
                error_data=pre_flight_service.fatal_errors
            ))

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))
