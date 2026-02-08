from pydantic import BaseModel
from typing import Dict, Optional, Any
from datetime import datetime
from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    assignment_id: int
    user_id: str
    username: str
    # Map: "main.py" -> "print('hello')"
    files: Dict[str, str]


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    user_id: str
    status: SubmissionStatus
    final_score: Optional[float] = None
    created_at: datetime

    # TODO: Evaluate if return result tree or not.
    result_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True