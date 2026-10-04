import logging
from abc import ABC, abstractmethod
from autograder.translations import t

from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.evaluation_error import EvaluationError

logger = logging.getLogger(__name__)


class Step(ABC):
    """
    Abstract base class for all pipeline steps.
    """
    @property
    @abstractmethod
    def step_name(self) -> StepName:
        """Return the name of the step (e.g. StepName.GRADE)."""

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute the step on the pipeline execution context.
        This provides a shared error-handling wrapper catching unexpected exceptions
        and logging them, marking the step status as INTERRUPTED.
        """
        locale = pipeline_exec.locale
        try:
            return self._execute(pipeline_exec)
        except EvaluationError as e:
            logger.exception("Evaluation failed at %s", self.step_name.value)
            return pipeline_exec.add_step_result(StepResult(
                step=self.step_name, data=None, status=StepStatus.INTERRUPTED,
                error=e.message, error_code=e.code, error_category=e.category,
                retryable=e.retryable,
            ))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Step %s was interrupted: %s", self.step_name.value, str(e))
            
            error_msg = "The grading execution could not complete."
            
            return pipeline_exec.add_step_result(
                StepResult(
                    step=self.step_name,
                    data=None,
                    status=StepStatus.INTERRUPTED,
                    error=error_msg,
                    error_code="EXECUTION_ERROR",
                    original_input=pipeline_exec
                )
            )

    @abstractmethod
    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Internal execution logic to be implemented by subclasses."""
