from typing import Dict, Optional
from dataclasses import dataclass
from sandbox_manager.models.sandbox_models import Language

@dataclass
class SubmissionFile:
    """Represents a single file in a submission."""
    filename: str
    content: str

@dataclass
class Submission:
    """Represents a student's submission for an assignment."""
    username: str
    user_id: int
    assignment_id: int
    submission_files: Dict[str,SubmissionFile]
    language: Optional[Language] = None
    locale: str = "en"
