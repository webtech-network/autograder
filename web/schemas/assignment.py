# Shared properties
from dataclasses import Field
from datetime import datetime
from typing import Optional, Dict, Any


class AssignmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    template_name: str = Field(..., description="Key of the template to use, e.g., 'python_scripts'")

    grading_criteria = None
    feedback_preferences = None
    setup_config = None
    # TODO: Define these fields with appropriate types

# Properties to return to client
class AssignmentResponse(AssignmentBase):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

