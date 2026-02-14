"""Schemas package."""

from web.schemas.assignment import (
    GradingConfigCreate,
    GradingConfigUpdate,
    GradingConfigResponse,
)
from web.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionDetailResponse,
    SubmissionStatus,
)

__all__ = [
    "GradingConfigCreate",
    "GradingConfigUpdate",
    "GradingConfigResponse",
    "SubmissionCreate",
    "SubmissionResponse",
    "SubmissionDetailResponse",
    "SubmissionStatus",
]
