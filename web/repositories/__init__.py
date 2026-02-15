"""Repository pattern implementations."""

from web.repositories.base_repository import BaseRepository
from web.repositories.grading_config_repository import GradingConfigRepository
from web.repositories.submission_repository import SubmissionRepository
from web.repositories.result_repository import ResultRepository

__all__ = [
    "BaseRepository",
    "GradingConfigRepository",
    "SubmissionRepository",
    "ResultRepository",
]
