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

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Build a criteria tree from the configuration and template.

        Args:
            pipeline_exec: Template containing test functions

        Returns:
            StepResult containing the built CriteriaTree
        """
        try:
            logger.info("Building criteria tree (user=%s)", pipeline_exec.submission.username)
            # Validate criteria configuration
            criteria_config = CriteriaConfig.from_dict(self._criteria_json)
            template = pipeline_exec.get_step_result(StepName.LOAD_TEMPLATE).data
            # Build the criteria tree with embedded test functions
            criteria_tree = self._criteria_tree_service.build_tree(
                criteria_config,
                template
            )
            logger.info(
                "Criteria tree built successfully (user=%s)",
                pipeline_exec.submission.username,
            )

            return pipeline_exec.add_step_result(StepResult(
                step=StepName.BUILD_TREE,
                data=criteria_tree,
                status=StepStatus.SUCCESS,
                original_input=pipeline_exec
            ))

        except Exception as e:
            logger.error(
                "Failed to build criteria tree: %s (user=%s)",
                str(e),
                pipeline_exec.submission.username,
            )
            return pipeline_exec.add_step_result(StepResult(
                step=StepName.BUILD_TREE,
                data=None,
                status=StepStatus.FAIL,
                error=f"Failed to build criteria tree: {str(e)}",
                original_input=pipeline_exec
            ))
