"""Submission schemas for API requests and responses."""

from datetime import datetime
from autograder.models.contracts.definition import GradingDefinition
from autograder.models.contracts.outcome import TerminalOutcome, OutcomeError
from autograder.models.contracts.provenance import DefinitionProvenance
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, StrictInt, field_validator, model_validator

from sandbox_manager.models.sandbox_models import Language
from submission_contract import (
    MAX_FILES, MAX_TOTAL_FILE_BYTES, MAX_TOTAL_METADATA_BYTES,
    validate_filename, validate_content, validate_filenames, validate_metadata, metadata_bytes,
)


class SubmissionStatus(str, Enum):
    """Status of a submission."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionFileData(BaseModel):
    """Schema for a submission file."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., strict=True, description="Canonical relative POSIX path")
    content: str = Field(..., strict=True, description="Exact UTF-8 source text")
    changed_lines: Optional[List[StrictInt]] = Field(
        None,
        description="One-indexed line numbers added or modified in this file",
    )
    file_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional opaque metadata for this file",
    )


    _filename = field_validator("filename")(validate_filename)
    _content = field_validator("content")(validate_content)
    _metadata = field_validator("file_metadata")(validate_metadata)

    @model_validator(mode="after")
    def valid_changed_lines(self):
        """Line numbers refer to actual lines; empty differs from unspecified."""
        if self.changed_lines is not None:
            if len(self.changed_lines) != len(set(self.changed_lines)):
                raise ValueError("changed_lines must not contain duplicates")
            line_count = len(self.content.splitlines())
            if any(line < 1 or line > line_count for line in self.changed_lines):
                raise ValueError("changed_lines must name existing one-based lines")
        return self


class EvaluationScopeData(BaseModel):
    """Schema defining the files that are the primary evaluation subject."""

    model_config = ConfigDict(extra="forbid")

    scoped_files: List[str] = Field(
        ..., min_length=1, max_length=MAX_FILES,
        description="Filenames to include in scope-aware pipeline analysis",
    )


    @field_validator("scoped_files")
    @classmethod
    def valid_scope(cls, value):
        """Scope has the same names as source files, without aliases or duplicates."""
        for name in value:
            validate_filename(name)
        validate_filenames(value)
        return value


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
    """Schema for creating a new submission."""

    model_config = ConfigDict(extra="forbid")
    external_assignment_id: str = Field(..., min_length=1, max_length=255, strict=True, description="External assignment ID")
    external_user_id: str = Field(..., min_length=1, max_length=255, strict=True, description="External user ID")
    username: str = Field(..., min_length=1, max_length=255, strict=True, description="Username of the submitter")
    files: List[SubmissionFileData] = Field(..., min_length=1, max_length=MAX_FILES, description="List of source files to submit")
    language: Optional[str] = Field(None, description="Optional language override")
    locale: Optional[str] = Field(
        "en", max_length=32, description="Optional locale for feedback (e.g., 'en', 'pt_br')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional submission metadata"
    )
    evaluation_scope: Optional[EvaluationScopeData] = Field(
        None,
        description="Optional file scope for pipeline analysis",
    )

    _metadata = field_validator("metadata")(validate_metadata)

    @model_validator(mode="after")
    def valid_file_set(self):
        """Validate the complete accepted input before any job is created."""
        names = [file.filename for file in self.files]
        validate_filenames(names)
        if sum(len(file.content.encode("utf-8")) for file in self.files) > MAX_TOTAL_FILE_BYTES:
            raise ValueError("submission source exceeds 5 MiB total")
        total_metadata = metadata_bytes(self.metadata) + sum(
            metadata_bytes(file.file_metadata) for file in self.files
        )
        if total_metadata > MAX_TOTAL_METADATA_BYTES:
            raise ValueError("submission metadata exceeds 64 KiB total")
        if self.evaluation_scope and not set(self.evaluation_scope.scoped_files).issubset(names):
            raise ValueError("evaluation_scope must name submitted files")
        return self

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
                "Unsupported language. "
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


class SubmissionFileDetail(BaseModel):
    """Stored source projection; legacy records are not revalidated as new input."""

    filename: str
    content: str
    changed_lines: list[int] | None = None
    file_metadata: dict | None = None


class SubmissionDetailResponse(SubmissionResponse):
    """Authenticated source, provenance and outcome projection."""

    submission_files: Dict[str, SubmissionFileDetail]
    locale: str = "en"
    evaluation_scope: EvaluationScopeData | None = None
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

    _metadata = field_validator("submission_metadata")(validate_metadata)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value):
        """Require a canonical language for host attestations."""
        if value not in {language.value for language in Language}:
            raise ValueError(
                "Language must be a canonical supported language identifier"
            )
        return value


class ExternalResultResponse(BaseModel):
    """Receipt for a validated external host attestation."""

    submission_id: int
    grading_config_id: int
    status: SubmissionStatus
    final_score: float | None
    language: str
    provenance: DefinitionProvenance
    graded_at: datetime
    execution_time_ms: int
