from abc import ABC, abstractmethod
from typing import Any


class Step(ABC):
    @abstractmethod
    def execute(self, input: Any) -> Any:
        pass

