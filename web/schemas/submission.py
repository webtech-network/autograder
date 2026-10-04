"""Submission schemas for API requests and responses."""

from datetime import datetime
from autograder.models.contracts.definition import GradingDefinition
from autograder.models.contracts.outcome import TerminalOutcome, OutcomeError
from autograder.models.contracts.provenance import DefinitionProvenance
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator

from sandbox_manager.models.sandbox_models import Language


class SubmissionStatus(str, Enum):
    """Status of a submission."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionFileData(BaseModel):
    """Schema for a submission file."""

    filename: str = Field(..., description="Name of the file")
    content: str = Field(..., description="Content of the file")
    changed_lines: Optional[List[int]] = Field(
        None,
        description="One-indexed line numbers added or modified in this file",
    )
    file_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional opaque metadata for this file",
    )


class EvaluationScopeData(BaseModel):
    """Schema defining the files that are the primary evaluation subject."""

    scoped_files: List[str] = Field(
        ...,
        description="Filenames to include in scope-aware pipeline analysis",
    )


class TestDeltaResponse(BaseModel):
    """Schema for a single test delta in a baseline comparison."""

    path: str = Field(
        ..., description="Stable test path string (category/subject/.../test_name)"
    )
    status: str = Field(
        ...,
        description="Status transition: improved, regressed, unchanged, introduced, or removed",
    )
    baseline_score: Optional[float] = Field(None, description="Score in baseline run")
    head_score: Optional[float] = Field(None, description="Score in head run")
    delta: Optional[float] = Field(None, description="Score change (head - baseline)")


class ComparisonResultResponse(BaseModel):
    """Schema for baseline comparison results."""

    score_delta: float = Field(..., description="Overall final score change")
    improved: bool = Field(..., description="True if score_delta > 0")
    test_deltas: List[TestDeltaResponse] = Field(
        default_factory=list, description="Per-test deltas"
    )


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Schema for creating a new submission."""
    external_assignment_id: str = Field(..., description="External assignment ID")
    external_user_id: str = Field(..., description="External user ID")
    username: str = Field(..., description="Username of the submitter")
    files: List[SubmissionFileData] = Field(..., description="List of files to submit")
    language: Optional[str] = Field(None, description="Optional language override")
    locale: Optional[str] = Field(
        "en", description="Optional locale for feedback (e.g., 'en', 'pt_br')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional submission metadata"
    )
    evaluation_scope: Optional[EvaluationScopeData] = Field(
        None,
        description="Optional file scope for pipeline analysis",
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the language is supported."""
        if v is None:
            return v

        # Normalize to uppercase for comparison
        language_upper = v.upper()

        # Check if language exists in Language enum
        valid_languages = [lang.name for lang in Language]
        if language_upper not in valid_languages:
            valid_languages_lower = [lang.value for lang in Language]
            raise ValueError(
                f"Unsupported language '{v}'. "
                f"Supported languages are: {', '.join(valid_languages_lower)}"
            )

        # Return the lowercase value (as stored in the enum)
        return Language[language_upper].value


class SubmissionResponse(BaseModel):
    """Compact status/history projection; source files and tree require details."""

    id: int
    grading_config_id: int
    external_user_id: str
    username: str
    language: str | None
    status: SubmissionStatus
    submitted_at: datetime
    graded_at: datetime | None = None
    final_score: float | None = None
    execution_time_ms: int | None = None
    provenance: DefinitionProvenance | None = None
    provenance_status: str
    error: OutcomeError | None = None
    feedback_status: str | None = None
    comparison_status: str | None = None


class SubmissionDetailResponse(SubmissionResponse):
    submission_files: Dict[str, str]
    submission_metadata: dict | None = None
    definition_snapshot: GradingDefinition | None = None
    outcome: TerminalOutcome | None = None
    diagnostics: dict | None = None


class ExternalResultCreate(BaseModel):
    """Authenticated host attestation using the shared outcome and exact definition."""

    model_config = ConfigDict(extra="forbid")
    grading_config_id: int = Field(gt=0, strict=True)
    external_user_id: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    language: str
    definition_snapshot: GradingDefinition
    outcome: TerminalOutcome
    submission_metadata: dict | None = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value):
        if value not in {language.value for language in Language}:
            raise ValueError(
                "Language must be a canonical supported language identifier"
            )
        return value


class ExternalResultResponse(BaseModel):
    submission_id: int
    grading_config_id: int
    status: SubmissionStatus
    final_score: float | None
    language: str
    provenance: DefinitionProvenance
    graded_at: datetime
    execution_time_ms: int
