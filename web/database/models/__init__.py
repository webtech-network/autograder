"""Database models initialization."""

from web.database.models.grading_config import GradingConfiguration
from web.database.models.submission import Submission
from web.database.models.submission_result import SubmissionResult

__all__ = ["GradingConfiguration", "Submission", "SubmissionResult"]
