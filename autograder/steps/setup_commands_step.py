import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName, StepCategory
from autograder.services.pre_flight_service import PreFlightService
from autograder.translations import t

logger = logging.getLogger(__name__)

class SetupCommandsStep(Step):
    """
    Executes compilation and environment setup commands inside the sandbox.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config

    @property
    def step_name(self) -> StepName:
        return StepName.SETUP_COMMANDS

    @property
    def step_category(self) -> StepCategory:
        return StepCategory.SETUP

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        submission_language = pipeline_exec.submission.language
        
        template_result = pipeline_exec.get_step_result(StepName.LOAD_TEMPLATE)
        template = template_result.data if template_result and template_result.is_successful else None
        
        template_required_files = template.required_files if template else None
        template_setup_commands = template.setup_commands if template else None

        pre_flight_service = PreFlightService(
            self._setup_config, 
            submission_language, 
            locale=pipeline_exec.locale,
            template_required_files=template_required_files,
            template_setup_commands=template_setup_commands
        )

        if pre_flight_service.setup_commands:
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
                error_msg = "\n".join(pre_flight_service.get_error_messages()) if pre_flight_service.has_errors() else t("preflight.error.unknown", locale=pipeline_exec.locale)
                logger.warning("Setup commands failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg,
                    error_data=pre_flight_service.fatal_errors
                ))

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))
