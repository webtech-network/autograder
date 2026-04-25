from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, TYPE_CHECKING, cast
import time

from autograder.models.dataclass.grading_result import GradingResult
from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.submission import Submission

if TYPE_CHECKING:
    from autograder.models.abstract.template import Template
    from autograder.models.criteria_tree import CriteriaTree
    from autograder.models.dataclass.focus import Focus
    from autograder.models.dataclass.grade_step_result import GradeStepResult
    from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
    from autograder.models.result_tree import ResultTree
    from sandbox_manager.sandbox_container import SandboxContainer


class PipelineStatus(Enum):
    """
    Status of the autograder pipeline execution.
    """
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

    @property
    def locale(self) -> str:
        """Returns the locale for this pipeline execution, sourced from the submission."""
        return self.submission.locale

    def add_step_result(self, step_result: StepResult) -> 'PipelineExecution':
        """
        Adds a single StepResult to the list of execution results.

        Args:
            step_result: The result objects to be added.
        Returns:
            The current PipelineExecution instance for chaining.
        """
        self.step_results.append(step_result)
        return self



    def get_step_result(self, step_name: StepName) -> StepResult:
        """
        Retrieves the StepResult for a given step name.

        Args:
            step_name: The StepName to look for.
        Returns:
            The corresponding StepResult.
        Raises:
            ValueError: If the step result was not found.
        """
        for step_result in self.step_results:
            if step_result.step == step_name:
                return step_result
        raise ValueError(f"Step {step_name} was not executed in the pipeline.")

    def has_step_result(self, step_name: StepName) -> bool:
        """
        Checks if the pipeline result contains record of a given step execution.

        Args:
            step_name: The StepName to check.
        Returns:
            True if step result exists, False otherwise.
        """
        return any(step_result.step == step_name for step_result in self.step_results)

    def _require_step_data(self, step_name: StepName, artifact_name: str) -> Any:
        step_result = self.get_step_result(step_name)
        if step_result.data is None:
            raise ValueError(
                f"Step {step_name.value} did not produce required {artifact_name} data."
            )
        return step_result.data

    def get_loaded_template(self) -> "Template":
        """
        Retrieves the Grading Template object loaded for this execution.
        """
        return cast(
            "Template",
            self._require_step_data(StepName.LOAD_TEMPLATE, "template"),
        )

    def get_built_criteria_tree(self) -> "CriteriaTree":
        """
        Retrieves the CriteriaTree object generated from the grading criteria.
        """
        return cast(
            "CriteriaTree",
            self._require_step_data(StepName.BUILD_TREE, "criteria tree"),
        )

    def get_structural_analysis_result(self) -> Optional["StructuralAnalysisResult"]:
        """
        Retrieves the StructuralAnalysisResult object if it was produced during the pipeline.
        """
        if not self.has_step_result(StepName.STRUCTURAL_ANALYSIS):
            return None
        from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
        return cast(
            StructuralAnalysisResult,
            self._require_step_data(StepName.STRUCTURAL_ANALYSIS, "structural analysis result"),
        )

    def get_sandbox(self) -> Optional["SandboxContainer"]:
        """
        Retrieves the SandboxContainer object if it was created during the pipeline.
        """
        return self.sandbox

    def get_grade_step_result(self) -> "GradeStepResult":
        """
        Retrieves the GradeStepResult object produced by the grading step.
        """
        return cast(
            "GradeStepResult",
            self._require_step_data(StepName.GRADE, "grade result"),
        )

    def get_result_tree(self) -> "ResultTree":
        """
        Retrieves the ResultTree object containing the grading results.
        """
        return cast("ResultTree", self.get_grade_step_result().result_tree)

    def get_ai_batch_results(self) -> Optional[dict]:
        """
        Retrieves the AI batch results dict produced by AiBatchStep, or None if
        the step was not part of this pipeline execution.
        """
        if not self.has_step_result(StepName.AI_BATCH):
            return None
        return cast(Optional[dict], self.get_step_result(StepName.AI_BATCH).data)

    def get_focus(self) -> "Focus":
        """
        Retrieves the Focus object identified for the submission.
        """
        return cast(
            "Focus",
            self._require_step_data(StepName.FOCUS, "focus"),
        )

    def get_feedback(self) -> Optional[str]:
        """
        Retrieves the feedback string if feedback generation step was executed.
        """
        if not self.has_step_result(StepName.FEEDBACK):
            return None
        return cast(Optional[str], self.get_step_result(StepName.FEEDBACK).data)

    def get_previous_step(self) -> Optional[StepResult]:
        """
        Retrieves the result of the last executed step in the pipeline.
        """
        return self.step_results[-1] if self.step_results else None

    def set_failure(self):
        """
        Marks the pipeline execution status as FAILED.
        """
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
        """
        Initializes a new PipelineExecution with the submission data.

        Args:
            submission: The submission to be graded.
        Returns:
            A new PipelineExecution instance starting from the BOOTSTRAP step.
        """
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
