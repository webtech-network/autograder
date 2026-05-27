import logging

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName, StepCategory
from autograder.models.config.setup import SetupConfig
from autograder.services.assets.resolver import AssetSourceResolver
from autograder.translations import t

logger = logging.getLogger(__name__)

class AssetInjectionStep(Step):
    """
    Handles moving static assets into the sandbox.
    """

    def __init__(self, setup_config):
        self._setup_config = SetupConfig.from_dict(setup_config) if isinstance(setup_config, dict) else (setup_config or SetupConfig())
        self._asset_resolver = AssetSourceResolver() if self._setup_config.assets else None

    @property
    def step_name(self) -> StepName:
        return StepName.ASSET_INJECTION

    @property
    def step_category(self) -> StepCategory:
        return StepCategory.SETUP

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
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

        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))
