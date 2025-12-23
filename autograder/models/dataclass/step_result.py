from dataclasses import dataclass
from typing import Any, Optional

# This should be a generic
@dataclass
class StepResult:
    data: Any
    error: Optional[str] = None
    failed_at_step: Optional[str] = None
    original_input: Any = None

    @property
    def is_successful(self) -> bool:
        return self.error is None