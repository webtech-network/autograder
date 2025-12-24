from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepResult, StepStatus
from autograder.services.pre_flight_service import PreFlightService


class PreFlightStep(Step):
    """
    Pre-flight check step that validates submission before grading begins.

    Checks are run in order:
    1. Required files check
    2. Setup commands check (only if files check passes)

    If any check fails, the step returns a FAIL status with error details.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config
        self._pre_flight_service = PreFlightService(setup_config)

    def execute(self, input) -> StepResult:
        """
        Execute pre-flight checks on the submission.

        Args:
            input: Submission data (typically file list or submission object)

        Returns:
            StepResult with status SUCCESS if all checks pass, FAIL otherwise
        """
        # Check required files first
        if self._setup_config.get('required_files'):
            files_ok = self._pre_flight_service.check_required_files(input)
            if not files_ok:
                # File check failed, don't continue to setup commands
                return StepResult(
                    data=input,
                    status=StepStatus.FAIL,
                    error=self._format_errors(),
                    failed_at_step=self.__class__.__name__,
                    original_input=input
                )

        # Check setup commands only if file check passed
        if self._setup_config.get('setup_commands'):
            setup_ok = self._pre_flight_service.check_setup_commands()
            if not setup_ok:
                return StepResult(
                    data=input,
                    status=StepStatus.FAIL,
                    error=self._format_errors(),
                    failed_at_step=self.__class__.__name__,
                    original_input=input
                )

        # All checks passed
        return StepResult(
            data=input,
            status=StepStatus.SUCCESS,
            original_input=input
        )

    def _format_errors(self) -> str:
        """Format all preflight errors into a single error message."""
        if not self._pre_flight_service.has_errors():
            return "Unknown preflight error"

        error_messages = self._pre_flight_service.get_error_messages()
        return "\n".join(error_messages)

