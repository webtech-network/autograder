import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.services.sandbox_service import SandboxService
from autograder.translations import t

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
            # Sandbox creation failed, error details are already logged in the service
            logger.error("Sandbox creation failed (external_user_id=%s)", pipeline_exec.submission.user_id)
            lang_val = pipeline_exec.submission.language.value if pipeline_exec.submission.language else "unknown"
            return pipeline_exec.add_step_result(StepResult.fail(
                step=self.step_name,
                error=t("preflight.error.sandbox_creation_failed", locale=pipeline_exec.locale, language=lang_val, error="See logs for details")
            ))

        # Store sandbox in PipelineExecution for downstream steps and cleanup
        pipeline_exec.sandbox = sandbox
        logger.info("Sandbox created and attached to pipeline (external_user_id=%s)", pipeline_exec.submission.user_id)

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, sandbox))
