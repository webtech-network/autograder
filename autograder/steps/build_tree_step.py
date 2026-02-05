from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.models.abstract.step import Step
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName


class BuildTreeStep(Step):
    """
    Step that builds a CriteriaTree from validated criteria configuration.

    This step is used when grading multiple submissions with the same criteria.
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

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """
        Build a criteria tree from the configuration and template.

        Args:
            input: Template containing test functions

        Returns:
            StepResult containing the built CriteriaTree
        """
        try:
            # Validate criteria configuration
            criteria_config = CriteriaConfig.from_dict(self._criteria_json)
            template = input.get_step_result(StepName.LOAD_TEMPLATE).data
            # Build the criteria tree with embedded test functions
            criteria_tree = self._criteria_tree_service.build_tree(
                criteria_config,
                template
            )

            return input.add_step_result(StepResult(
                step="BuildTreeStep",
                data=criteria_tree,
                status=StepStatus.SUCCESS,
                original_input=input
            ))

        except Exception as e:
            return input.add_step_result(StepResult(
                step="BuildTreeStep",
                data=None,
                status=StepStatus.FAIL,
                error=f"Failed to build criteria tree: {str(e)}",
                original_input=input
            ))
