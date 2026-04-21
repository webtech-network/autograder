from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic
from enum import Enum

T = TypeVar("T")


class StepStatus(Enum):
    """
    Enumeration of possible step execution statuses.
    
    - SUCCESS: The step executed successfully to completion.
    - FAIL: The step executed to completion but the result was a logical failure 
            (e.g., student submission failed pre-flight, code failed to compile).
    - INTERRUPTED: The step encountered an unexpected system-level error or unhandled 
                   exception preventing it from concluding properly.
    """
    SUCCESS = "success"
    FAIL = "fail"
    INTERRUPTED = "interrupted"


class StepName(Enum):
    """Enumeration of all available pipeline steps."""
    BOOTSTRAP = "BootstrapStep"
    LOAD_TEMPLATE = "LoadTemplateStep"
    BUILD_TREE = "BuildTreeStep"
    PRE_FLIGHT = "PreFlightStep"
    SANDBOX = "SandboxStep"
    AI_BATCH = "AiBatchStep"
    STRUCTURAL_ANALYSIS = "StructuralAnalysisStep"
    GRADE = "GradeStep"
    FOCUS = "FocusStep"
    FEEDBACK = "FeedbackStep"
    EXPORTER = "ExporterStep"


@dataclass
class StepResult(Generic[T]):
    """Represents the result of a single pipeline step execution."""
    step: StepName
    data: T
    status: StepStatus = StepStatus.SUCCESS
    error: Optional[str] = None
    error_data: Any = None
    original_input: Any = None

    @property
    def is_successful(self) -> bool:
        """Checks if the step execution was successful and has no errors."""
        return self.status == StepStatus.SUCCESS and self.error is None

    @classmethod
    def success(cls, step: StepName, data: T) -> "StepResult[T]":
        """Creates a successful StepResult."""
        return cls(step=step, data=data, status=StepStatus.SUCCESS)

    @classmethod
    def fail(cls, step: StepName, error: str, data: Optional[T] = None, error_data: Any = None) -> "StepResult[T]":
        """Creates a failed StepResult."""
        return cls(step=step, data=data, status=StepStatus.FAIL, error=error, error_data=error_data)
