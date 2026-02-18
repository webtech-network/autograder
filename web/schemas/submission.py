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
