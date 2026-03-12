import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
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

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute pre-flight checks on the submission, returns a reference to the sandbox if the grading process requires it.

        Args:
            pipeline_exec: PipelineExecution containing submission data

        Returns:
            StepResult with status SUCCESS if all checks pass, FAIL otherwise
        """
        # Create PreFlightService with submission language for language-specific config resolution
        submission_language = pipeline_exec.submission.language
        self._pre_flight_service = PreFlightService(self._setup_config, submission_language)

        logger.info(
            "Pre-flight checks started: external_user_id=%s, language=%s",
            pipeline_exec.submission.user_id,
            submission_language.value if submission_language else "none",
        )

        sandbox = None
        # Check required files first
        submission_files = pipeline_exec.submission.submission_files
        # Use the resolved required_files from the service (language-specific)
        if self._pre_flight_service.required_files:
            logger.info(
                "Checking required files: %s (external_user_id=%s)",
                self._pre_flight_service.required_files,
                pipeline_exec.submission.user_id,
            )
            files_ok = self._pre_flight_service.check_required_files(submission_files)
            if not files_ok:
                # File check failed, don't continue to setup commands
                error_msg = self._format_errors()
                logger.warning(
                    "Required files check failed: %s (external_user_id=%s)",
                    error_msg,
                    pipeline_exec.submission.user_id,
                )
                return pipeline_exec.add_step_result(StepResult(
                        step=StepName.PRE_FLIGHT,
                        data=sandbox,  # sandbox is None here, which is correct
                        status=StepStatus.FAIL,
                        error=error_msg,
                        original_input=pipeline_exec
                        ))

        grading_template = pipeline_exec.get_step_result(StepName.LOAD_TEMPLATE).data
        if grading_template.requires_sandbox:
            logger.info("Creating sandbox for submission (external_user_id=%s)", pipeline_exec.submission.user_id)
            sandbox = self._pre_flight_service.create_sandbox(pipeline_exec.submission) # Needs error handling?
            logger.info("Sandbox created successfully (external_user_id=%s)", pipeline_exec.submission.user_id)

        # Check setup commands only if file check passed
        # Use the resolved setup_commands from the service (language-specific)
        if self._pre_flight_service.setup_commands:
            logger.info(
                "Running setup commands (external_user_id=%s)",
                pipeline_exec.submission.user_id,
            )
            setup_ok = self._pre_flight_service.check_setup_commands(sandbox)
            if not setup_ok:
                # self._pre_flight_service.destroy_sandbox(sandbox) #TODO: Decide when to destroy sandbox (Maybe after grading process finishes?
                error_msg = self._format_errors()
                logger.warning(
                    "Setup commands check failed: %s (external_user_id=%s)",
                    error_msg,
                    pipeline_exec.submission.user_id,
                )
                return pipeline_exec.add_step_result(StepResult(
                    step=StepName.PRE_FLIGHT,
                    data=sandbox,#Return Sandbox Here anyway? (How to deal with sandbox destruction)
                    status=StepStatus.FAIL,
                    error=error_msg,
                    original_input=pipeline_exec
                ))

        # All checks passed
        logger.info("Pre-flight checks passed (external_user_id=%s)", pipeline_exec.submission.user_id)
        return pipeline_exec.add_step_result(StepResult(
            step=StepName.PRE_FLIGHT,
            data=sandbox,
            status=StepStatus.SUCCESS,
            original_input=pipeline_exec
        ))

    def _format_errors(self) -> str:
        """Format all preflight errors into a single error message."""
        if not self._pre_flight_service.has_errors():
            return "Unknown preflight error"
        error_messages = self._pre_flight_service.get_error_messages()
        return "\n".join(error_messages)

