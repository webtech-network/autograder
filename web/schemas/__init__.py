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
    SubmissionFileData,
    EvaluationScopeData,
    ExternalResultCreate,
    ExternalResultResponse,
    SubmissionComparisonResponse,
)
from web.schemas.execution import (
    DeliberateCodeExecutionRequest,
    DeliberateCodeExecutionResponse,
)

__all__ = [
    "GradingConfigCreate",
    "GradingConfigUpdate",
    "GradingConfigResponse",
    "SubmissionCreate",
    "SubmissionResponse",
    "SubmissionDetailResponse",
    "SubmissionStatus",
    "SubmissionFileData",
    "EvaluationScopeData",
    "ExternalResultCreate",
    "ExternalResultResponse",
    "SubmissionComparisonResponse",
    "DeliberateCodeExecutionRequest",
    "DeliberateCodeExecutionResponse",
]
