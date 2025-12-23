from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepResult


class ExporterStep(Step):
    def __init__(self, remote_driver):
        self._remote_driver = remote_driver # UpstashDriver
    def execute(self, input) -> StepResult:
        pass