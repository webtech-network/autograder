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
    start_time: float = field(default_factory=time.time)  # Track execution time

    def add_step_result(self, step_result: StepResult) -> 'PipelineExecution':
        self.step_results.append(step_result)
        return self

    def get_pipeline_execution_summary(self) -> Dict[str, Any]:
        """
        Generate a detailed summary of the pipeline execution for API responses.

        Returns:
            Dictionary containing execution status, steps, and error details
        """
        execution_time_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0

        # Determine failed step if any
        failed_step = None
        for step in self.step_results:
            if step.status == StepStatus.FAIL:
                failed_step = step.step.value
                break

        # Build step details
        steps = []
        for step in self.step_results:
            if step.step == StepName.BOOTSTRAP:
                continue  # Skip bootstrap step in output

            step_info = {
                "name": step.step.value,
                "status": step.status.value,
            }

            # Add execution time if available
            if hasattr(step, 'execution_time_ms'):
                step_info["execution_time_ms"] = step.execution_time_ms

            # Add success message for completed steps
            if step.status == StepStatus.SUCCESS:
                if step.step == StepName.LOAD_TEMPLATE:
                    step_info["message"] = "Template loaded successfully"
                elif step.step == StepName.BUILD_TREE:
                    step_info["message"] = "Criteria tree built successfully"
                elif step.step == StepName.PRE_FLIGHT:
                    step_info["message"] = "All preflight checks passed"
                elif step.step == StepName.GRADE:
                    if self.result and self.result.final_score is not None:
                        step_info["message"] = f"Grading completed: {self.result.final_score}/100"
                    else:
                        step_info["message"] = "Grading completed"
                elif step.step == StepName.FEEDBACK:
                    step_info["message"] = "Feedback generated"
                elif step.step == StepName.EXPORTER:
                    step_info["message"] = "Results exported"

            # Add error details for failed steps
            elif step.status == StepStatus.FAIL and step.error:
                step_info["message"] = step.error.split('\n')[0]  # First line of error
                step_info["error_details"] = self._extract_error_details(step)

            steps.append(step_info)

        # Count planned vs completed steps
        total_planned = 7  # BOOTSTRAP, LOAD_TEMPLATE, BUILD_TREE, PRE_FLIGHT, GRADE, FEEDBACK, EXPORT
        completed = len([s for s in self.step_results if s.step != StepName.BOOTSTRAP])

        return {
            "status": self.status.value if self.status != PipelineStatus.EMPTY else "unknown",
            "failed_at_step": failed_step,
            "total_steps_planned": total_planned,
            "steps_completed": completed,
            "execution_time_ms": execution_time_ms,
            "steps": steps
        }

    def _extract_error_details(self, step: StepResult) -> Dict[str, Any]:
        """Extract structured error details from a failed step."""
        error_details = {}

        if step.step == StepName.PRE_FLIGHT:
            # Parse preflight errors
            error_text = step.error

            # Check if it's a missing file error
            if "Arquivo ou diretório obrigatório não encontrado" in error_text or "Required file" in error_text:
                error_details["error_type"] = "required_file_missing"
                error_details["phase"] = "required_files"
                # Extract file name if possible
                if "`'" in error_text:
                    start = error_text.find("`'") + 2
                    end = error_text.find("'`", start)
                    if end > start:
                        error_details["missing_file"] = error_text[start:end]

            # Check if it's a setup command error
            elif "Setup command" in error_text:
                error_details["error_type"] = "setup_command_failed"
                error_details["phase"] = "setup_commands"

                # Extract command name
                if "Setup command '" in error_text:
                    start = error_text.find("Setup command '") + 15
                    end = error_text.find("' failed", start)
                    if end > start:
                        error_details["command_name"] = error_text[start:end]

                # Extract command
                if "**Command:** `" in error_text:
                    start = error_text.find("**Command:** `") + 14
                    end = error_text.find("`", start)
                    if end > start:
                        if "failed_command" not in error_details:
                            error_details["failed_command"] = {}
                        error_details["failed_command"]["command"] = error_text[start:end]

                # Extract exit code
                if "exit code " in error_text:
                    try:
                        start = error_text.find("exit code ") + 10
                        end = start
                        while end < len(error_text) and error_text[end].isdigit():
                            end += 1
                        if end > start:
                            if "failed_command" not in error_details:
                                error_details["failed_command"] = {}
                            error_details["failed_command"]["exit_code"] = int(error_text[start:end])
                    except (ValueError, IndexError):
                        pass

                # Extract stderr
                if "**Error Output (stderr):**" in error_text:
                    start = error_text.find("**Error Output (stderr):**") + 26
                    # Find the code block
                    start = error_text.find("```", start) + 3
                    end = error_text.find("```", start)
                    if end > start:
                        if "failed_command" not in error_details:
                            error_details["failed_command"] = {}
                        error_details["failed_command"]["stderr"] = error_text[start:end].strip()

                # Extract stdout if present
                if "**Output (stdout):**" in error_text:
                    start = error_text.find("**Output (stdout):**") + 20
                    start = error_text.find("```", start) + 3
                    end = error_text.find("```", start)
                    if end > start:
                        if "failed_command" not in error_details:
                            error_details["failed_command"] = {}
                        error_details["failed_command"]["stdout"] = error_text[start:end].strip()

        return error_details

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
        if not self.has_step_result(StepName.PRE_FLIGHT):
            return None
        return cast(
            Optional["SandboxContainer"],
            self.get_step_result(StepName.PRE_FLIGHT).data,
        )

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
