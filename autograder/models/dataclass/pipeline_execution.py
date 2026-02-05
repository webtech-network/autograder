from dataclasses import dataclass
from typing import List, Optional

from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.submission import Submission


@dataclass
class PipelineExecution:
    """
    Main object of the autograder pipeline, keeps track of the execution and step results.

    Attributes:
        step_results (list): A list of StepResult objects representing the results of each step in the pipeline.
        assignment_id (str): The unique identifier for the assignment being graded.
        submission (Submission): The submission being processed in the pipeline.
    """
    step_results: List[StepResult]
    assignment_id: int
    submission: Submission

    def add_step_result(self, step_result: StepResult) -> 'PipelineExecution':
        self.step_results.append(step_result)
        return self

    def get_step_result(self, step_name: StepName) -> StepResult:
        for step_result in self.step_results:
            if step_result.step == step_name:
                return step_result
        raise ValueError(f"Step {step_name} was not executed in the pipeline.")

    def get_previous_step(self) -> Optional[StepResult]:
        return self.step_results[-1] if self.step_results else None

    @classmethod
    def create_pipeline_obj(cls, submission: Submission) -> 'PipelineExecution':
        bootstrap = StepResult(
            step=StepName.BOOTSTRAP,
            data=submission,
            status=StepStatus.SUCCESS)
        pipeline_execution = PipelineExecution(step_results=[], assignment_id=submission.assignment_id,
                                               submission=submission)
        pipeline_execution.add_step_result(bootstrap)
        return pipeline_execution
