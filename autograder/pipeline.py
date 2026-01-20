from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepResult, StepStatus


class AutograderPipeline:
    def __init__(self):
        self._steps = []

    def add_step(self, step: Step) -> None:
        self._steps.append(step)

    def run(self, input_data:'Submission'):
        result = StepResult(data=input_data, status=StepStatus.SUCCESS, original_input=input_data) #Initialize result object with input data
        print(result)
        for step in self._steps:
            print("Executing step:", step.__class__.__name__)
            if not result.is_successful:
                break
            try:
                result = step.execute(result.data)
            except Exception as e:
                result.error = str(e)
                result.status = StepStatus.FAIL
                result.failed_at_step = step.__class__.__name__

        if not result.is_successful:
            return GradingResult( #Maybe return a ErrorResponse object?
                final_score=0.0,
                status="error",
                feedback=None,
                result_tree=None,
                error=result.error,
                failed_at_step=result.failed_at_step,
            )
        else:
            return result.data # Assuming the final step returns a GradingResult



