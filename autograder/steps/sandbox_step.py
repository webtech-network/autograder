import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
from autograder.services.pre_flight_service import PreFlightService

logger = logging.getLogger(__name__)


class SandboxStep(Step):
    """
    The Sandbox step is responsible for:
        - Creating a sandbox environment if required by the template.
        - Preparing the workdir with submission files.
        - Executing setup commands.
        - Attaching the sandbox to the PipelineExecution for use by downstream steps.
    """

    def __init__(self, setup_config):
        self._setup_config = setup_config
        self._pre_flight_service = None

    @property
    def step_name(self) -> StepName:
        return StepName.SANDBOX

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute sandbox acquisition and setup.

        Args:
            pipeline_exec: PipelineExecution context.

        Returns:
            PipelineExecution with updated sandbox and step result.
        """
        submission_language = pipeline_exec.submission.language
        self._pre_flight_service = PreFlightService(self._setup_config, submission_language)

        grading_template = pipeline_exec.get_loaded_template()
        
        if not grading_template.requires_sandbox:
            logger.info("Template does not require a sandbox. Skipping SandboxStep.")
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

        logger.info("Creating sandbox for submission (external_user_id=%s)", pipeline_exec.submission.user_id)
        sandbox = self._pre_flight_service.create_sandbox(pipeline_exec.submission)
        
        if sandbox is None:
            # Sandbox creation failed, errors are in the service
            error_msg = self._format_errors()
            logger.error("Sandbox creation failed: %s", error_msg)
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=error_msg,
                error_data=self._pre_flight_service.fatal_errors
            ))

        # Store sandbox in PipelineExecution for downstream steps and cleanup
        pipeline_exec.sandbox = sandbox
        logger.info("Sandbox created and attached to pipeline (external_user_id=%s)", pipeline_exec.submission.user_id)

        # Run setup commands if they exist
        if self._pre_flight_service.setup_commands:
            logger.info("Running setup commands in sandbox (external_user_id=%s)", pipeline_exec.submission.user_id)
            setup_ok = self._pre_flight_service.check_setup_commands(sandbox)
            
            if not setup_ok:
                error_msg = self._format_errors()
                logger.warning("Setup commands failed: %s", error_msg)
                return pipeline_exec.add_step_result(StepResult.fail(
                    step=self.step_name,
                    error=error_msg,
                    error_data=self._pre_flight_service.fatal_errors
                ))

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, sandbox))

    def _format_errors(self) -> str:
        """Format all errors from the preflight service into a single message."""
        if not self._pre_flight_service.has_errors():
            return "Unknown sandbox error"
        return "\n".join(self._pre_flight_service.get_error_messages())
