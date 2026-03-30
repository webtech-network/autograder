import logging

from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.models.abstract.step import Step
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName

logger = logging.getLogger(__name__)


class BuildTreeStep(Step):
    """
    Step that builds a CriteriaTree from validated criteria configuration.

    The tree is built once and reused for efficiency.
    """

    def __init__(self, criteria_json: dict):
        """
        Initialize the build tree step.

        Args:
            criteria_json: Raw criteria configuration dictionary
        """
        self._criteria_json = criteria_json
        self._criteria_tree_service = CriteriaTreeService()

    @property
    def step_name(self) -> StepName:
        return StepName.BUILD_TREE

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Build a criteria tree from the configuration and template.

        Args:
            pipeline_exec: Template containing test functions

        Returns:
            StepResult containing the built CriteriaTree
        """
        logger.info("Building criteria tree (external_user_id=%s)", pipeline_exec.submission.user_id)
        # Validate criteria configuration
        criteria_config = CriteriaConfig.from_dict(self._criteria_json)
        template = pipeline_exec.get_loaded_template()
        # Build the criteria tree with embedded test functions
        criteria_tree = self._criteria_tree_service.build_tree(
            criteria_config,
            template
        )
        logger.info(
            "Criteria tree built successfully (external_user_id=%s)",
            pipeline_exec.submission.user_id,
        )

        return pipeline_exec.add_step_result(StepResult(
            step=StepName.BUILD_TREE,
            data=criteria_tree,
            status=StepStatus.SUCCESS,
            original_input=pipeline_exec
        ))
