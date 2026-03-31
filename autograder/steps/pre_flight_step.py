import logging
from typing import List

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.services.pre_flight_service import PreFlightService
from autograder.translations import t

logger = logging.getLogger(__name__)


class PreFlightStep(Step):
    """
    The Pre-flight step is responsible for:
        - Running Pre-Grading validations on submissions
        - Executing setup commands (e.g., compilation) in the sandbox

    Pre-Grading Checks are run in order:
    1. Required files check
    2. Setup commands check (only if files check passes and sandbox exists)

    If any check fails, the step returns a FAIL status with error details.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config
        self._pre_flight_service = None

    @property
    def step_name(self) -> StepName:
        return StepName.PRE_FLIGHT

    def _execute(self, pipeline_exec: PipelineExecution, locale: Optional[str] = None) -> PipelineExecution:
        """
        Execute pre-flight checks (required files) and setup commands.
        
        Note: Sandbox must have been created in a previous step (SandboxStep).
        """
        submission_language = pipeline_exec.submission.language
        self._pre_flight_service = PreFlightService(self._setup_config, submission_language, locale=locale)

        logger.info(
            "Pre-flight checks started: external_user_id=%s, language=%s",
            pipeline_exec.submission.user_id,
            submission_language.value if submission_language else "none",
        )

        # 1. Check required files
        if self._pre_flight_service.required_files:
            logger.info("Checking required files for submission (external_user_id=%s)", pipeline_exec.submission.user_id)
            files_ok = self._pre_flight_service.check_required_files(pipeline_exec.submission.submission_files)
            
            if not files_ok:
                error_msg = self._format_errors()
                logger.warning("Required files check failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg,
                    error_data=self._pre_flight_service.fatal_errors
                ))

        # 2. Check setup commands (requires sandbox from a previous step)
        if self._pre_flight_service.setup_commands:
            sandbox = pipeline_exec.sandbox
            if not sandbox:
                # If SandboxStep was skipped but we have commands, we must report an error.
                error_msg = t("preflight.error.missing_sandbox", locale=locale)
                logger.error("Sandbox required for setup commands but was not found in pipeline execution.")
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg
                ))

            logger.info("Running setup commands in sandbox (external_user_id=%s)", pipeline_exec.submission.user_id)
            setup_ok = self._pre_flight_service.check_setup_commands(sandbox)
            
            if not setup_ok:
                error_msg = self._format_errors()
                logger.warning("Setup commands failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg,
                    error_data=self._pre_flight_service.fatal_errors
                ))

        logger.info("Pre-flight checks passed (external_user_id=%s)", pipeline_exec.submission.user_id)
        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

    def _format_errors(self) -> str:
        """Format all errors from PreFlightService into a single message."""
        if self._pre_flight_service and self._pre_flight_service.has_errors():
            return "\n".join(self._pre_flight_service.get_error_messages())
        
        locale = self._pre_flight_service.locale if self._pre_flight_service else None
        return t("preflight.error.unknown", locale=locale)
