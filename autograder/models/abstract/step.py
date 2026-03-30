import logging
from abc import ABC, abstractmethod

from autograder.models.dataclass.step_result import StepResult, StepStatus, StepName
from autograder.models.pipeline_execution import PipelineExecution

logger = logging.getLogger(__name__)


class Step(ABC):
    @property
    @abstractmethod
    def step_name(self) -> StepName:
        """Return the name of the step (e.g. StepName.GRADE)."""
        pass

    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Execute the step on the pipeline execution context.
        This provides a shared error-handling wrapper catching unexpected exceptions
        and logging them, marking the step status as INTERRUPTED.
        """
        try:
            return self._execute(pipeline_exec)
        except Exception as e:
            logger.exception("Step %s was interrupted: %s", self.step_name.value, str(e))
            return pipeline_exec.add_step_result(
                StepResult(
                    step=self.step_name,
                    data=None,
                    status=StepStatus.INTERRUPTED,
                    error=f"Step execution interrupted: {str(e)}",
                    original_input=pipeline_exec
                )
            )

    @abstractmethod
    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Internal execution logic to be implemented by subclasses."""
        pass

