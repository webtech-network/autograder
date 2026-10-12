"""Optional observations, never inputs to grading or terminal finalization."""
from dataclasses import dataclass
from typing import Callable, Literal

from autograder.models.contracts.outcome import OutcomeError


@dataclass(frozen=True)
class DiagnosticEvent:
    """A safe operational observation without grading data or back-references."""
    execution_id: str
    operation: str
    status: Literal["completed", "failed"]
    error: OutcomeError | None = None


DiagnosticObserver = Callable[[DiagnosticEvent], None]
