from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from sandbox_manager.models.sandbox_models import Language


@dataclass
class SubmissionFile:
    """Represents a single file in a submission."""
    filename: str
    content: str
    changed_lines: Optional[Set[int]] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_contribution_aware(self) -> bool:
        """Return whether changed-line information was supplied for this file."""
        return self.changed_lines is not None


@dataclass
class EvaluationScope:
    """
    Defines which files are the primary subject of an evaluation.

    When present, pipeline analysis steps restrict their work to these files.
    When absent, all submission files are treated equally.
    """

    scoped_files: List[str]


@dataclass
class Submission:
    """Represents a student's submission for an assignment."""
    username: str
    user_id: int
    assignment_id: int
    submission_files: Dict[str, SubmissionFile]
    language: Optional[Language] = None
    locale: str = "en"
    evaluation_scope: Optional[EvaluationScope] = None
