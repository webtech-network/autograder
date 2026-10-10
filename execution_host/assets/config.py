from pydantic import BaseModel, Field, field_validator


class AssetConfig(BaseModel):
    """Configuration for a static asset to be injected into the sandbox."""
    source: str = Field(..., description="Relative path for the asset on the S3 provider")
    target: str = Field(..., description="Absolute path for the asset inside the container")
    read_only: bool = Field(True, description="Whether the asset should be read-only (0444)")

    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate the source path of the asset."""
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
        """Validate the target path of the asset."""
        if not v:
            raise ValueError("target must not be empty")
        if not v.startswith('/'):
            raise ValueError("target must be an absolute path (starting with /)")
        if '..' in v:
            raise ValueError("target must not contain path traversal (..)")
        return v
