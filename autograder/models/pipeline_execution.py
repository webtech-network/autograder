from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING, cast
import time

from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.submission import Submission

if TYPE_CHECKING:
    from autograder.models.abstract.template import Template
    from autograder.models.criteria_tree import CriteriaTree
    from autograder.models.dataclass.focus import Focus
    from autograder.models.dataclass.grade_step_result import GradeStepResult
    from autograder.models.result_tree import ResultTree
    from sandbox_manager.sandbox_container import SandboxContainer


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
    sandbox: Optional["SandboxContainer"] = field(default=None, init=False)
    start_time: float = field(default_factory=time.time)  # Track execution time

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

    def _require_step_data(self, step_name: StepName, artifact_name: str) -> Any:
        step_result = self.get_step_result(step_name)
        if step_result.data is None:
            raise ValueError(
                f"Step {step_name.value} did not produce required {artifact_name} data."
            )
        return step_result.data

    def get_loaded_template(self) -> "Template":
        return cast(
            "Template",
            self._require_step_data(StepName.LOAD_TEMPLATE, "template"),
        )

    def get_built_criteria_tree(self) -> "CriteriaTree":
        return cast(
            "CriteriaTree",
            self._require_step_data(StepName.BUILD_TREE, "criteria tree"),
        )

    def get_sandbox(self) -> Optional["SandboxContainer"]:
        return self.sandbox

    def get_grade_step_result(self) -> "GradeStepResult":
        return cast(
            "GradeStepResult",
            self._require_step_data(StepName.GRADE, "grade result"),
        )

    def get_result_tree(self) -> "ResultTree":
        return cast("ResultTree", self.get_grade_step_result().result_tree)

    def require_focus(self) -> "Focus":
        return cast(
            "Focus",
            self._require_step_data(StepName.FOCUS, "focus"),
        )

    def get_focus(self) -> Optional["Focus"]:
        if not self.has_step_result(StepName.FOCUS):
            return None
        return cast(Optional["Focus"], self.get_step_result(StepName.FOCUS).data)

    def get_feedback(self) -> Optional[str]:
        if not self.has_step_result(StepName.FEEDBACK):
            return None
        return cast(Optional[str], self.get_step_result(StepName.FEEDBACK).data)

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
            grade_result = self.get_grade_step_result()
            feedback = self.get_feedback()
            if self.has_step_result(StepName.FEEDBACK) and feedback is None:
                raise ValueError("Feedback step exists but produced no feedback content.")
            grading_result = GradingResult(
                final_score=grade_result.final_score,
                feedback=feedback,
                result_tree=grade_result.result_tree,
                focus=self.get_focus(),
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
