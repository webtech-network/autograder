"""Submission schemas for API requests and responses."""

from datetime import datetime
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


class SubmissionCreate(BaseModel):
    """Schema for creating a new submission."""
    external_assignment_id: str = Field(..., description="External assignment ID")
    external_user_id: str = Field(..., description="External user ID")
    username: str = Field(..., description="Username of the submitter")
    files: List[SubmissionFileData] = Field(..., description="List of files to submit")
    language: Optional[str] = Field(None, description="Optional language override")
    locale: Optional[str] = Field("en", description="Optional locale for feedback (e.g., 'en', 'pt_br')")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional submission metadata")

    @field_validator('language')
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
    """Schema for submission response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    grading_config_id: int
    external_user_id: str
    username: str
    language: Optional[str] = None
    status: SubmissionStatus
    submitted_at: datetime
    graded_at: Optional[datetime] = None
    final_score: Optional[float] = None
    feedback: Optional[str] = None
    result_tree: Optional[Dict[str, Any]] = None
    focus: Optional[Dict[str, Any]] = None


class SubmissionDetailResponse(SubmissionResponse):
    """Detailed submission response including files."""
    submission_files: Dict[str, str]
    submission_metadata: Optional[Dict[str, Any]] = None
    pipeline_execution: Optional[Dict[str, Any]] = None  # NEW: Detailed pipeline execution info


class ExternalResultStatus(str, Enum):
    """Status of an externally graded submission."""
    COMPLETED = "completed"
    FAILED = "failed"


class ExternalResultCreate(BaseModel):
    """Schema for ingesting externally computed grading results."""
    grading_config_id: int = Field(..., description="Internal grading configuration ID")
    external_user_id: str = Field(..., description="External user ID from LMS/platform")
    username: str = Field(..., description="Username of the submitter")
    language: str = Field(..., description="Language the submission was graded in")
    status: ExternalResultStatus = Field(..., description="Grading outcome: completed or failed")
    final_score: float = Field(..., description="Final grading score", ge=0.0)
    feedback: Optional[str] = Field(None, description="Generated feedback text")
    result_tree: Optional[Dict[str, Any]] = Field(None, description="Scored result tree")
    focus: Optional[Dict[str, Any]] = Field(None, description="Sorted failed tests by impact")
    pipeline_execution: Optional[Dict[str, Any]] = Field(None, description="Pipeline step execution details")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds", ge=0)
    error_message: Optional[str] = Field(None, description="Error message for failed runs")
    submission_metadata: Optional[Dict[str, Any]] = Field(None, description="Repository/run metadata")

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that the language is supported."""
        language_upper = v.upper()
        valid_languages = [lang.name for lang in Language]
        if language_upper not in valid_languages:
            valid_languages_lower = [lang.value for lang in Language]
            raise ValueError(
                f"Unsupported language '{v}'. "
                f"Supported languages are: {', '.join(valid_languages_lower)}"
            )
        return Language[language_upper].value


class ExternalResultResponse(BaseModel):
    """Response after ingesting an external grading result."""
    model_config = ConfigDict(from_attributes=True)

    submission_id: int
    grading_config_id: int
    external_user_id: str
    username: str
    status: SubmissionStatus
    final_score: float
    graded_at: datetime
    execution_time_ms: int
