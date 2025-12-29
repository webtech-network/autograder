from typing import Dict, Any, Union
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.dataclass.step_result import StepResult, StepStatus
from autograder.models.abstract.step import Step
from autograder.models.abstract.template import Template
from autograder.models.dataclass.criteria_config import CriteriaConfig
from autograder.services.grader_service import GraderService


class GradeStep(Step):
    """
    Step that grades a submission using either a CriteriaTree or raw criteria configuration.

    This step intelligently determines which grading method to use:
    - If input is CriteriaTree: Use grade_from_tree (for multiple submissions)
    - If input is Template: Use grade_from_config (for single submission)
    """

    def __init__(self, criteria_json: dict = None, submission_files: Dict[str, Any] = None, submission_id: str = None):
        """
        Initialize the grade step.

        Args:
            criteria_json: Raw criteria configuration (only needed for single submission mode)
            submission_files: Student submission files
            submission_id: Optional identifier for the submission
        """
        self._criteria_json = criteria_json
        self._submission_files = submission_files
        self._submission_id = submission_id
        self._grader_service = GraderService()

    def execute(self, input: Union[CriteriaTree, Template]) -> StepResult[GradingResult]:
        """
        Grade a submission based on the input type.

        Args:
            input: Either a CriteriaTree (multi-submission mode) or Template (single submission mode)

        Returns:
            StepResult containing GradingResult with scores and result tree
        """
        try:
            # Determine which grading method to use based on input type
            if isinstance(input, CriteriaTree):
                # Multi-submission mode: grade from pre-built tree
                result_tree = self._grader_service.grade_from_tree(
                    criteria_tree=input,
                    submission_files=self._submission_files,
                    submission_id=self._submission_id
                )
            elif isinstance(input, Template):
                # Single submission mode: grade directly from config
                if not self._criteria_json:
                    raise ValueError("criteria_json is required when grading from template")

                # Validate criteria configuration
                criteria_config = CriteriaConfig.from_dict(self._criteria_json)

                # Grade directly from config (one-pass)
                result_tree = self._grader_service.grade_from_config(
                    criteria_config=criteria_config,
                    template=input,
                    submission_files=self._submission_files,
                    submission_id=self._submission_id
                )
            else:
                raise ValueError(
                    f"Invalid input type for GradeStep: {type(input).__name__}. "
                    f"Expected CriteriaTree or Template"
                )

            # Create grading result
            final_score = result_tree.calculate_final_score()

            grading_result = GradingResult(
                final_score=final_score,
                status="success",
                result_tree=result_tree
            )

            return StepResult(
                data=grading_result,
                status=StepStatus.SUCCESS,
                original_input=input
            )

        except Exception as e:
            # Return error result
            grading_result = GradingResult(
                final_score=0.0,
                status="error",
                error=f"Grading failed: {str(e)}",
                failed_at_step=self.__class__.__name__
            )

            return StepResult(
                data=grading_result,
                status=StepStatus.FAIL,
                error=str(e),
                failed_at_step=self.__class__.__name__,
                original_input=input
            )



