from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.submission import Submission


class PipelineStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    EMPTY = "empty"

@dataclass
class PipelineExecution:
    """
    Main object of the autograder pipeline, keeps track of the grading execution and step results.

    Attributes:
        step_results (list): A list of StepResult objects representing the results of each step in the pipeline.
        assignment_id (str): The unique identifier for the assignment being graded.
        submission (Submission): The submission being processed in the pipeline.
    """
    step_results: List[StepResult]
    assignment_id: int
    submission: Submission
    status: PipelineStatus = PipelineStatus.EMPTY
    result: Optional[GradingResult] = None

    def add_step_result(self, step_result: StepResult) -> 'PipelineExecution':
        self.step_results.append(step_result)
        return self

    def get_step_result(self, step_name: StepName) -> StepResult:
        for step_result in self.step_results:
            if step_result.step == step_name:
                return step_result
        raise ValueError(f"Step {step_name} was not executed in the pipeline.")

    def has_step_result(self, step_name: StepName) -> bool:
        return any(step_result.step == step_name for step_result in self.step_results)

    def get_previous_step(self) -> Optional[StepResult]:
        return self.step_results[-1] if self.step_results else None

    def set_failure(self):
        self.status = PipelineStatus.FAILED

    def finish_execution(self):
        """
        Set Pipeline status to SUCCESS if it is not already FAILED

        If pipeline succeeds, sets the result object with the final grading result and feedback (if available) for easy retrieval.
        """
        grading_result = None
        if self.status != PipelineStatus.FAILED:
            self.status = PipelineStatus.SUCCESS
            grading_result = GradingResult(
                final_score=self.get_step_result(StepName.GRADE).data.final_score,
                feedback=self.get_step_result(StepName.FEEDBACK).data if self.has_step_result(StepName.FEEDBACK) else None,
                result_tree=self.get_step_result(StepName.GRADE).data.result_tree
            )
        self.result = grading_result


    @classmethod
    def start_execution(cls, submission: Submission) -> 'PipelineExecution':

        bootstrap = StepResult(
            step=StepName.BOOTSTRAP,
            data=submission,
            status=StepStatus.SUCCESS)

        pipeline_execution = PipelineExecution(step_results=[],
                                               assignment_id=submission.assignment_id,
                                               status=PipelineStatus.RUNNING,
                                               submission=submission)

        pipeline_execution.add_step_result(bootstrap)
        return pipeline_execution
