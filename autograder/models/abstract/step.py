from abc import ABC, abstractmethod
from typing import Any

from autograder.models.dataclass.step_result import StepResult


class Step(ABC):
    @abstractmethod
    def execute(self, input: Any) -> StepResult[Any]:
        pass

