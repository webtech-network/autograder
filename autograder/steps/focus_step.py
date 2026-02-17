from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.result_tree import ResultTree
from autograder.services.focus_service import FocusService


class FocusStep(Step):
    """
    Step that gets the main subjects to be analyzed by the AI
    """

    def __init__(self, trim_service: FocusService) -> None:
        self.__focus_service = trim_service

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """
        Trim the result tree to get the main points of failure
        Args:
            input: PipelineExecution containtin the grading result from the GRADE step
        Returns:
            PipelineExecution with an added StepResult indicating success or failure of the trimming step
        """

        try:
            result_tree = input.get_step_result(StepName.GRADE).data.result_tree
            main_subjects = self.__focus_service.find(result_tree)

            return input.add_step_result(
                StepResult(
                    step=StepName.FOCUS,
                    data=main_subjects,
                    status=StepStatus.SUCCESS,
                )
            )
        except Exception as e:
            return input.add_step_result(
                StepResult(
                    step=StepName.FOCUS, data=None, status=StepStatus.FAIL, error=str(e)
                )
            )
