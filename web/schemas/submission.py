"""Submission schemas for API requests and responses."""

from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class SubmissionStatus(str, Enum):
    """Status of a submission."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionCreate(BaseModel):
    """Schema for creating a new submission."""
    external_assignment_id: str = Field(..., description="External assignment ID")
    external_user_id: str = Field(..., description="External user ID")
    username: str = Field(..., description="Username of the submitter")
    files: Dict[str, str] = Field(..., description="Map of filename to file content")
    language: Optional[str] = Field(None, description="Optional language override")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional submission metadata")


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


class SubmissionDetailResponse(SubmissionResponse):
    """Detailed submission response including files."""
    submission_files: Dict[str, str]
    submission_metadata: Optional[Dict[str, Any]] = None
