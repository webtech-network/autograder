from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic
from enum import Enum

T = TypeVar('T')


class StepStatus(Enum):
    SUCCESS = "success"
    FAIL = "fail"


@dataclass
class StepResult(Generic[T]):
    data: T
    status: StepStatus = StepStatus.SUCCESS
    error: Optional[str] = None
    failed_at_step: Optional[str] = None
    original_input: Any = None

    @property
    def is_successful(self) -> bool:
        return self.status == StepStatus.SUCCESS and self.error is None
