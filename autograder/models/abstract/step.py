from abc import ABC, abstractmethod

from autograder.models.pipeline_execution import PipelineExecution


class Step(ABC):
    @abstractmethod
    def execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """Execute the step on the pipeline execution context."""

