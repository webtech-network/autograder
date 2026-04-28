from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class AssetConfig(BaseModel):
    """Configuration for a static asset to be injected into the sandbox."""
    source: str = Field(..., description="Relative path for the asset on the S3 provider")
    target: str = Field(..., description="Absolute path for the asset inside the container")
    read_only: bool = Field(True, description="Whether the asset should be read-only (0444)")

    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        if not v:
            raise ValueError("source must not be empty")
        if v.startswith('/'):
            raise ValueError("source must be a relative path")
        if '..' in v:
            raise ValueError("source must not contain path traversal (..)")
        return v

    @field_validator('target')
    @classmethod
    def validate_target(cls, v: str) -> str:
        if not v:
            raise ValueError("target must not be empty")
        if not v.startswith('/'):
            raise ValueError("target must be an absolute path (starting with /)")
        if '..' in v:
            raise ValueError("target must not contain path traversal (..)")
        return v


class LanguageSetupConfig(BaseModel):
    """Language-specific setup configuration."""
    required_files: List[str] = Field(default_factory=list)
    setup_commands: List[Any] = Field(default_factory=list)


class SetupConfig(BaseModel):
    """Root configuration for sandbox setup, including global assets and language-specific configs."""
    assets: List[AssetConfig] = Field(default_factory=list)
    
    # Language-specific configurations are handled dynamically
    # but we can provide hints for common languages
    python: Optional[LanguageSetupConfig] = None
    java: Optional[LanguageSetupConfig] = None
    node: Optional[LanguageSetupConfig] = None
    cpp: Optional[LanguageSetupConfig] = None

    # Allow extra fields for other languages
    model_config = {"extra": "allow"}

    @model_validator(mode='before')
    @classmethod
    def handle_global_key(cls, data: Any) -> Any:
        """Handle the 'global' key sent by the backend and map it to 'assets'."""
        if isinstance(data, dict) and "global" in data:
            global_data = data["global"]
            if isinstance(global_data, dict) and "assets" in global_data:
                # If we have global.assets, use them
                data["assets"] = global_data["assets"]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SetupConfig":
        """Create and validate setup config from dictionary."""
        return cls.model_validate(data or {})
