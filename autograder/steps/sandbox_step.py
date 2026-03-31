import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)


class SandboxStep(Step):
    """
    The Sandbox step is responsible for:
        - Creating a sandbox environment if required by the template.
        - Preparing the workdir with submission files.
        - Attaching the sandbox to the PipelineExecution for use by downstream steps.
        
    Note: Setup commands are now executed in the PreFlightStep to keep validations centralized.
    """

    def __init__(self):
        self._sandbox_service = SandboxService()

    @property
    def step_name(self) -> StepName:
        return StepName.SANDBOX

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute sandbox acquisition and preparation.

        Args:
            pipeline_exec: PipelineExecution context.

        Returns:
            PipelineExecution with updated sandbox and step result.
        """
        grading_template = pipeline_exec.get_loaded_template()
        
        if not grading_template.requires_sandbox:
            logger.info("Template does not require a sandbox. Skipping SandboxStep.")
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))

        logger.info("Creating sandbox for submission (external_user_id=%s)", pipeline_exec.submission.user_id)
        sandbox = self._sandbox_service.create_sandbox(pipeline_exec.submission)
        
        if sandbox is None:
            # Sandbox creation failed, errors are in the service
            error_msg = self._format_errors()
            logger.error("Sandbox creation failed: %s", error_msg)
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=error_msg,
                error_data=self._sandbox_service.fatal_errors
            ))

        # Store sandbox in PipelineExecution for downstream steps and cleanup
        pipeline_exec.sandbox = sandbox
        logger.info("Sandbox created and attached to pipeline (external_user_id=%s)", pipeline_exec.submission.user_id)

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, sandbox))

    def _format_errors(self) -> str:
        """Format all errors from the sandbox service into a single message."""
        if not self._sandbox_service.has_errors():
            return "Unknown sandbox error"
        return "\n".join(self._sandbox_service.get_error_messages())
