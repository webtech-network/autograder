from abc import ABC, abstractmethod

from autograder.models.dataclass.pipeline_execution import PipelineExecution


class Step(ABC):
    @abstractmethod
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        pass

