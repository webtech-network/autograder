from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PreflightCheckType(Enum):
    """Types of preflight checks that can fail."""
    FILE_CHECK = "file_check"
    SETUP_COMMAND = "setup_command"


@dataclass
class PreflightError:
    """
    Represents an error found during pre-flight checks.

    Attributes:
        type: The type of error (file check or setup command)
        message: The error message describing what went wrong
        details: Optional additional context about the error
    """
    type: PreflightCheckType
    message: str
    details: Optional[dict] = None
