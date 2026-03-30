import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.services.pre_flight_service import PreFlightService

logger = logging.getLogger(__name__)


class PreFlightStep(Step):
    """
    The Pre-flight step is responsible for:
        - Running Pre-Grading validations on submissions
        - Sandboxing Submission Code (If the grading process requires executing submission code)

    Pre-Grading Checks are run in order:
    1. Required files check
    2. Setup commands check (only if files check passes)

    If any check fails, the step returns a FAIL status with error details.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config
        self._pre_flight_service = None
        # Don't create service here, create it per-execution with language

    @property
    def step_name(self) -> StepName:
        return StepName.PRE_FLIGHT

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute pre-flight checks (required files) on the submission.

        Args:
            pipeline_exec: PipelineExecution context.

        Returns:
            PipelineExecution with updated step results.
        """
        submission_language = pipeline_exec.submission.language
        locale = pipeline_exec.submission.locale
        self._pre_flight_service = PreFlightService(self._setup_config, submission_language, locale=locale)

        logger.info(
            "Pre-flight (file check) started: external_user_id=%s, language=%s",
            pipeline_exec.submission.user_id,
            submission_language.value if submission_language else "none",
        )

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

        logger.info("Pre-flight (file check) passed (external_user_id=%s)", pipeline_exec.submission.user_id)
        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

    def _format_errors(self) -> str:
        """Format all preflight errors into a single error message."""
        if not self._pre_flight_service.has_errors():
            return "Unknown preflight error"
        error_messages = self._pre_flight_service.get_error_messages()
        return "\n".join(error_messages)
