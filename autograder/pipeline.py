from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepResult


class AutograderPipeline:
    def __init__(self):
        self._steps = []

    def add_step(self, step: Step) -> None:
        self._filters.append(step)

    def run(self, input_data):
        result = StepResult(data=input_data, original_input=input_data) #Initialize result object with input data

        for step in self._steps:
            if not result.is_successful:
                break
            try:
                result.data = step.execute(result.data)
            except Exception as e:
                result.error = str(e)
                result.failed_at_step = step.__class__.__name__

        if not result.is_successful:
            return GradingResult(
                final_score=0.0,
                status="error",
                feedback=None,
                result_tree=None,
                error=result.error,
                failed_at_step=result.failed_at_step,
            )
        else:
            return result.data # Assuming the final step returns a GradingResult (Which is bad)

