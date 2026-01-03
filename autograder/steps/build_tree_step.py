from autograder.services.criteria_tree_service import CriteriaTreeService
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.abstract.step import Step
from autograder.models.abstract.template import Template
from autograder.models.dataclass.criteria_config import CriteriaConfig
from autograder.models.dataclass.step_result import StepResult, StepStatus


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

    def execute(self, input: Template) -> StepResult[CriteriaTree]:
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

            # Build the criteria tree with embedded test functions
            criteria_tree = self._criteria_tree_service.build_tree(
                criteria_config,
                input
            )

            return StepResult(
                data=criteria_tree,
                status=StepStatus.SUCCESS,
                original_input=input
            )

        except Exception as e:
            return StepResult(
                data=None,
                status=StepStatus.FAIL,
                error=f"Failed to build criteria tree: {str(e)}",
                failed_at_step=self.__class__.__name__,
                original_input=input
            )
