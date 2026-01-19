from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepResult, StepStatus

class ExporterStep(Step):
    def __init__(self, remote_driver):
        self._remote_driver = remote_driver # UpstashDriver
    def execute(self, input) -> StepResult:
        try:
            # Extract username and score from input
            username = input.username
            score = input.score

            # Set the score using UpstashDriver
            self._remote_driver.set_score(username, score)

            # Return success result
            return StepResult(
                data={"username": username, "score": score},
                status=StepStatus.SUCCESS
            )
        except Exception as e:
            # Return failure result
            return StepResult(
                data=None,
                status=StepStatus.FAIL,
                error=str(e),
                failed_at_step="ExporterStep"
            )
