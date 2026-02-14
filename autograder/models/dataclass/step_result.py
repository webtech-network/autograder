from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic
from enum import Enum

T = TypeVar("T")


class StepStatus(Enum):
    SUCCESS = "success"
    FAIL = "fail"


class StepName(Enum):
    BOOTSTRAP = "BootstrapStep"
    LOAD_TEMPLATE = "LoadTemplateStep"
    BUILD_TREE = "BuildTreeStep"
    PRE_FLIGHT = "PreFlightStep"
    GRADE = "GradeStep"
    FOCUS = "FocusStep"
    FEEDBACK = "FeedbackStep"
    EXPORTER = "ExporterStep"


@dataclass
class StepResult(Generic[T]):
    step: StepName
    data: T
    status: StepStatus = StepStatus.SUCCESS
    error: Optional[str] = None
    original_input: Any = None

    @property
    def is_successful(self) -> bool:
        return self.status == StepStatus.SUCCESS and self.error is None
