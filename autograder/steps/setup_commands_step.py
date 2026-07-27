import logging
from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName, StepCategory
from autograder.services.pre_flight_service import PreFlightService
from autograder.translations import t

logger = logging.getLogger(__name__)


class SetupCommandsStep(Step):
    """
    Step responsible for executing setup commands (e.g., compilation) in the sandbox.
    Requires an existing sandbox in the pipeline execution context.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config

    @property
    def step_name(self) -> StepName:
        return StepName.SETUP_COMMANDS

    @property
    def category(self) -> StepCategory:
        return StepCategory.SETUP

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        submission_language = pipeline_exec.submission.language
        pre_flight_service = PreFlightService(self._setup_config, submission_language, locale=pipeline_exec.locale)

        if not pre_flight_service.setup_commands:
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

        sandbox = pipeline_exec.sandbox
        if not sandbox:
            error_msg = t("preflight.error.missing_sandbox", locale=pipeline_exec.locale)
            logger.error("Sandbox required for setup commands but was not found in pipeline execution.")
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=error_msg
            ))

        logger.info("Running setup commands in sandbox (external_user_id=%s)", pipeline_exec.submission.user_id)
        setup_ok = pre_flight_service.check_setup_commands(sandbox)

        if not setup_ok:
            error_msg = "\n".join(pre_flight_service.get_error_messages())
            logger.warning("Setup commands failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=error_msg,
                error_data=pre_flight_service.fatal_errors
            ))

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))
