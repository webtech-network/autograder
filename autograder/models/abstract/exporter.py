"""Abstract interface for grade exporters."""

from abc import ABC, abstractmethod
from typing import Optional


class Exporter(ABC):
    """
    Abstract base class for grade exporters.

    Any system that receives grading results (Upstash Redis, GitHub Classroom, etc.)
    must implement this interface to be usable with the pipeline's ExporterStep.
    """

    @abstractmethod
    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        """
        Export a grading result to an external system.

        Args:
            user_id: External identifier for the student.
            score: Final numeric score (0-100).
            feedback: Optional feedback text. Exporters may ignore this
                      if they only handle scores.
        """
        pass
