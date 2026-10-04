"""HTTP envelopes for the shared grading-definition contract."""

from datetime import datetime
from autograder.models.contracts.definition import GradingDefinition
from pydantic import BaseModel, ConfigDict, Field, model_validator


class GradingConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_assignment_id: str = Field(min_length=1, max_length=255)
    definition: GradingDefinition


class GradingConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: GradingDefinition | None = None
    is_active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def reject_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(
                    f"{field} cannot be null; omit it to preserve its value"
                )
        return self


class GradingConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_assignment_id: str
    definition: GradingDefinition | None
    definition_hash: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    migration_error: dict | None = None
