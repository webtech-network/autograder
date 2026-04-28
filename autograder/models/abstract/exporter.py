"""Abstract interface for grade exporters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.pipeline_execution import PipelineExecution


class Exporter(ABC):
    """
    Abstract base class for grade exporters.

    Any system that receives grading results (Upstash Redis, GitHub Classroom, etc.)
    must implement this interface to be usable with the pipeline's ExporterStep.

    Subclasses that need access to the full pipeline execution (result tree,
    focus data, execution time, etc.) should override
    :meth:`export_with_context` instead of — or in addition to — :meth:`export`.
    The default implementation of :meth:`export_with_context` extracts
    ``user_id``, ``score``, and ``feedback`` from the execution and delegates
    to :meth:`export`, so existing exporters require no changes.
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

    def export_with_context(self, pipeline_exec: "PipelineExecution") -> None:
        """
        Export a grading result with access to the full pipeline execution.

        Override this in exporters that require richer data (e.g., result
        tree, focus, execution time).  The default implementation extracts
        ``user_id``, ``score``, and ``feedback`` from *pipeline_exec* and
        delegates to :meth:`export`.

        Args:
            pipeline_exec: The completed :class:`~autograder.models.pipeline_execution.PipelineExecution`
                containing all step results.
        """
        user_id = pipeline_exec.submission.user_id
        score = pipeline_exec.get_grade_step_result().final_score
        feedback: Optional[str] = pipeline_exec.get_feedback()
        self.export(user_id, score, feedback)
