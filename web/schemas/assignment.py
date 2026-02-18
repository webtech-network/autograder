"""Grading configuration schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator

from sandbox_manager.models.sandbox_models import Language


class GradingConfigCreate(BaseModel):
    """Schema for creating a new grading configuration."""
    external_assignment_id: str = Field(..., description="External assignment ID from the LMS/platform")
    template_name: str = Field(..., description="Template to use (e.g., 'webdev', 'api', 'IO')")
    criteria_config: Dict[str, Any] = Field(..., description="Grading criteria tree configuration")
    language: str = Field(..., description="Programming language (python, java, node, cpp)")
    setup_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Setup configuration including required_files and setup_commands for preflight checks"
    )
    # TODO: Include feedback options

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that the language is supported."""
        if not v:
            raise ValueError("Language cannot be empty")

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

class GradingConfigUpdate(BaseModel):
    """Schema for updating a grading configuration."""
    template_name: Optional[str] = None
    criteria_config: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    setup_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

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


class GradingConfigResponse(BaseModel):
    """Schema for grading configuration response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    external_assignment_id: str
    template_name: str
    criteria_config: Dict[str, Any]
    language: str
    setup_config: Optional[Dict[str, Any]]
    version: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

