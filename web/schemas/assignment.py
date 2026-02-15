"""Grading configuration schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class GradingConfigCreate(BaseModel):
    """Schema for creating a new grading configuration."""
    external_assignment_id: str = Field(..., description="External assignment ID from the LMS/platform")
    template_name: str = Field(..., description="Template to use (e.g., 'webdev', 'api', 'IO')")
    criteria_config: Dict[str, Any] = Field(..., description="Grading criteria tree configuration")
    language: str = Field(..., description="Programming language (python, java, node, cpp)")


class GradingConfigUpdate(BaseModel):
    """Schema for updating a grading configuration."""
    template_name: Optional[str] = None
    criteria_config: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None


class GradingConfigResponse(BaseModel):
    """Schema for grading configuration response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    external_assignment_id: str
    template_name: str
    criteria_config: Dict[str, Any]
    language: str
    version: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

