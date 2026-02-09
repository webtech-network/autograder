from typing import Dict, Optional

from dataclasses import dataclass

from sandbox_manager.models.sandbox_models import Language


@dataclass
class SubmissionFile:
    filename: str
    content: str

@dataclass
class Submission:
    username: str
    user_id: int
    assignment_id: int
    submission_files: Dict[str,SubmissionFile]
    language: Optional[Language] = None