"""Grading configuration schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

from sandbox_manager.models.sandbox_models import Language


class GradingConfigCreate(BaseModel):
    """Schema for creating a new grading configuration."""
    external_assignment_id: str = Field(..., description="External assignment ID from the LMS/platform")
    template_name: str = Field(..., description="Template to use (e.g., 'webdev', 'api', 'IO')")
    criteria_config: Dict[str, Any] = Field(..., description="Grading criteria tree configuration")
    languages: List[str] = Field(..., description="Supported programming languages (python, java, node, cpp)")
    setup_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Setup configuration including required_files and setup_commands for preflight checks"
    )
    # TODO: Include feedback options

    @field_validator('languages')
    @classmethod
    def validate_languages(cls, v: List[str]) -> List[str]:
        """Validate that all languages are supported."""
        if not v or len(v) == 0:
            raise ValueError("At least one language must be specified")

        validated_languages = []
        valid_language_values = [lang.value for lang in Language]

        for lang in v:
            if not lang:
                raise ValueError("Language cannot be empty")

            # Normalize to uppercase for comparison
            language_upper = lang.upper()

            # Check if language exists in Language enum
            valid_languages = [l.name for l in Language]
            if language_upper not in valid_languages:
                raise ValueError(
                    f"Unsupported language '{lang}'. "
                    f"Supported languages are: {', '.join(valid_language_values)}"
                )

            # Return the lowercase value (as stored in the enum)
            validated_languages.append(Language[language_upper].value)

        # Remove duplicates while preserving order
        seen = set()
        unique_languages = []
        for lang in validated_languages:
            if lang not in seen:
                seen.add(lang)
                unique_languages.append(lang)

        return unique_languages

class GradingConfigUpdate(BaseModel):
    """Schema for updating a grading configuration."""
    template_name: Optional[str] = None
    criteria_config: Optional[Dict[str, Any]] = None
    languages: Optional[List[str]] = None
    setup_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator('languages')
    @classmethod
    def validate_languages(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate that all languages are supported."""
        if v is None:
            return v

        if len(v) == 0:
            raise ValueError("At least one language must be specified")

        validated_languages = []
        valid_language_values = [lang.value for lang in Language]

        for lang in v:
            if not lang:
                raise ValueError("Language cannot be empty")

            # Normalize to uppercase for comparison
            language_upper = lang.upper()

            # Check if language exists in Language enum
            valid_languages = [l.name for l in Language]
            if language_upper not in valid_languages:
                raise ValueError(
                    f"Unsupported language '{lang}'. "
                    f"Supported languages are: {', '.join(valid_language_values)}"
                )

            # Return the lowercase value (as stored in the enum)
            validated_languages.append(Language[language_upper].value)

        # Remove duplicates while preserving order
        seen = set()
        unique_languages = []
        for lang in validated_languages:
            if lang not in seen:
                seen.add(lang)
                unique_languages.append(lang)

        return unique_languages


class GradingConfigResponse(BaseModel):
    """Schema for grading configuration response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    external_assignment_id: str
    template_name: str
    criteria_config: Dict[str, Any]
    languages: List[str]
    setup_config: Optional[Dict[str, Any]]
    version: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

