from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.models.dataclass.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName


class AutograderPipeline:
    def __init__(self):
        self._steps = []

    def add_step(self, step: Step) -> None:
        self._steps.append(step)

    def run(self, input_data:'Submission'):
        result = StepResult(
            step=StepName.BOOTSTRAP,
            data=input_data,
            status=StepStatus.SUCCESS)
        #Initialize result object with input data
        pipeline_execution = PipelineExecution(step_results=[], assignment_id="assignment_123", submission=input_data) #Example assignment_id
        pipeline_execution.add_step_result(result)

        for step in self._steps:
            print("Executing step:", step.__class__.__name__)
            if not result.get_previous_step.is_successful:
                break
            try:
                result = step.execute(result)
            except Exception as e:
                StepResult(
                    step=step.__class__.__name__,
                    data=None,
                    status=StepStatus.FAIL,
                    error=str(e),
                )

        if not result.is_successful: #Change this to report a PipelineExecution error with result details
            return GradingResult( #Maybe return a ErrorResponse object?
                final_score=0.0,
                status="error",
                feedback=None,
                result_tree=None,
                error=result.error,
                failed_at_step=result.failed_at_step,
            )
        else:
            return result.get_step_result(StepName.GRADE).data # How to return with feedback? How to know when there's no feedback?



