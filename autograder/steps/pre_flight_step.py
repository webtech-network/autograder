import logging
from typing import List

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.services.pre_flight_service import PreFlightService
from autograder.translations import t

logger = logging.getLogger(__name__)


from autograder.models.config.setup import SetupConfig
from autograder.services.assets.resolver import AssetSourceResolver

class PreFlightStep(Step):
    """
    The Pre-flight step is responsible for:
        - Running Pre-Grading validations on submissions
        - Injecting static assets into the sandbox
        - Executing setup commands (e.g., compilation) in the sandbox

    Pre-Grading Checks are run in order:
    1. Required files check
    2. Assets injection (requires sandbox from StepName.SANDBOX)
    3. Setup commands check (only if files check passes and sandbox exists)

    If any check fails, the step returns a FAIL status with error details.
    """

    def __init__(self, setup_config):
        self._setup_config = SetupConfig.from_dict(setup_config)
        self._pre_flight_service = None
        self._asset_resolver = AssetSourceResolver()

    @property
    def step_name(self) -> StepName:
        return StepName.PRE_FLIGHT

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute pre-flight checks (required files, assets, setup commands).
        """
        submission_language = pipeline_exec.submission.language
        self._pre_flight_service = PreFlightService(self._setup_config, submission_language, locale=pipeline_exec.locale)

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

        # 2. Inject assets (requires sandbox)
        sandbox = pipeline_exec.sandbox
        if self._setup_config.assets:
            if not sandbox:
                error_msg = t("preflight.error.setup_command_missing_sandbox", locale=pipeline_exec.locale)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg
                ))

            logger.info("Injecting assets into sandbox (external_user_id=%s)", pipeline_exec.submission.user_id)
            try:
                resolved_assets = self._asset_resolver.resolve_assets(self._setup_config.assets)
                sandbox.inject_assets(resolved_assets)
            except Exception as e:
                error_msg = f"Failed to inject assets: {str(e)}"
                logger.error("Asset injection failed (external_user_id=%s): %s", pipeline_exec.submission.user_id, error_msg)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg
                ))

        # 3. Check setup commands (requires sandbox from a previous step)

        if self._pre_flight_service.setup_commands:
            sandbox = pipeline_exec.sandbox
            if not sandbox:
                # If SandboxStep was skipped but we have commands, we must report an error.
                error_msg = t("preflight.error.missing_sandbox", locale=pipeline_exec.locale)
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
