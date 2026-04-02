"""GitHub Classroom exporter that wraps the existing GithubActionService export logic."""

import logging
from typing import Optional, TYPE_CHECKING

from autograder.models.abstract.exporter import Exporter

if TYPE_CHECKING:
    from github_action.github_action_service import GithubActionService

logger = logging.getLogger(__name__)


class GithubClassroomExporter(Exporter):
    """
    Exporter implementation for GitHub Classroom.

    Wraps the existing GithubActionService.export_results() method,
    which notifies GitHub Classroom of the score and optionally commits
    feedback to the repository.
    """

    def __init__(self, github_action_service: "GithubActionService"):
        self._service = github_action_service

    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        """
        Export grading result to GitHub Classroom.

        Args:
            user_id: The student's identifier (not used directly — GitHub Classroom
                     identifies the student by the repository/workflow context).
            score: Final numeric score (0-100).
            feedback: Optional feedback text to commit as relatorio.md.
        """
        include_feedback = feedback is not None
        logger.info(
            "Exporting to GitHub Classroom: score=%.2f, include_feedback=%s",
            score,
            include_feedback,
        )
        self._service.export_results(score, include_feedback, feedback)
