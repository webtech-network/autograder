

from __future__ import annotations

import logging
import os
import time
from typing import Optional, TYPE_CHECKING

from autograder.models.abstract.exporter import Exporter
from github_action.cloud_client import CloudClient

if TYPE_CHECKING:
    from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus

logger = logging.getLogger(__name__)

class CloudExporter(Exporter):
    """
    Exporter implementation for the *external* GitHub Action execution mode.

    Builds a rich payload from the completed
    :class:`~autograder.models.pipeline_execution.PipelineExecution` and
    submits it to the Autograder Cloud
    ``POST /api/v1/submissions/external-results`` endpoint.

    Args:
        client: Configured :class:`~github_action.cloud_client.CloudClient`
            instance used to communicate with the cloud API.
        grading_config_id: The internal (integer) grading-configuration ID
            returned by the cloud API.  Used for server-side correlation.
        language: Submission language (e.g. ``"python"``, ``"java"``).
            Must match a value accepted by the cloud API.
        student_name: GitHub username / student identifier.  Used for both
            ``external_user_id`` and ``username`` fields in the payload.
    """

    def __init__(
        self,
        client: CloudClient,
        grading_config_id: int,
        language: str,
        student_name: str,
    ) -> None:
        self._client = client
        self._grading_config_id = grading_config_id
        self._language = language
        self._student_name = student_name

    # ---------------------------------------------------------------------------
# Exporter interface
# ---------------------------------------------------------------------------

    def export_with_context(self, pipeline_exec: "PipelineExecution") -> None:
        """
        Build and submit the full grading payload using the complete pipeline
        execution data.

        This is the primary entry point called by
        :class:`~autograder.steps.export_step.ExporterStep`.  It collects
        score, feedback, result tree, focus analysis, execution time, and
        GitHub context then calls
        :meth:`~github_action.cloud_client.CloudClient.submit_external_result`.

        Args:
            pipeline_exec: The completed pipeline execution.
        """
        payload = self._build_payload(pipeline_exec)
        logger.info(
            "Submitting external result for config %d: score=%.2f, status=%s",
            self._grading_config_id,
            payload.get("final_score", 0.0),
            payload.get("status"),
        )
        self._client.submit_external_result(payload)

    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        """
        Fallback export using only the minimal ``(user_id, score, feedback)``
        triple.  Called when :meth:`export_with_context` is not invoked
        directly (e.g. in tests that bypass the pipeline).
        """
        payload = self._build_minimal_payload(user_id, score, feedback)
        logger.info(
            "Submitting minimal external result for config %d: score=%.2f",
            self._grading_config_id,
            score,
        )
        self._client.submit_external_result(payload)

    def submit_failure(self, error_message: str, execution_time_ms: int = 0) -> None:
        """
        Submit a failure payload to the cloud API.

        Called when the grading pipeline fails before the
        :class:`~autograder.steps.export_step.ExporterStep` runs, so that the
        cloud still records a terminal state for the submission.

        Args:
            error_message: Human-readable description of the failure.
            execution_time_ms: Total elapsed time in milliseconds up to the
                point of failure.
        """
        payload = {
            "grading_config_id": self._grading_config_id,
            "external_user_id": self._student_name,
            "username": self._student_name,
            "language": self._language,
            "status": "failed",
            "final_score": 0.0,
            "execution_time_ms": execution_time_ms,
            "error_message": error_message,
            "submission_metadata": self._get_github_context(),
        }
        logger.info(
            "Submitting failure payload for config %d: %s",
            self._grading_config_id,
            error_message,
        )
        self._client.submit_external_result(payload)

    # ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

    def _build_payload(self, pipeline_exec: "PipelineExecution") -> dict:
        """
        Construct the full result payload matching the ``ExternalResultCreate``
        schema expected by ``POST /api/v1/submissions/external-results``.
        """
        status = "completed"
        error_message: Optional[str] = None

        try:
            final_score = pipeline_exec.get_grade_step_result().final_score
        except (ValueError, AttributeError) as exc:
            final_score = 0.0
            status = "failed"
            error_message = str(exc)

        feedback = pipeline_exec.get_feedback()

        result_tree_dict: Optional[dict] = None
        try:
            result_tree = pipeline_exec.get_result_tree()
            result_tree_dict = result_tree.to_dict()
        except (ValueError, AttributeError):
            pass

        focus_dict: Optional[dict] = None
        try:
            focus = pipeline_exec.get_focus()
            focus_dict = focus.to_dict()
        except (ValueError, AttributeError):
            pass

        execution_time_ms = int((time.time() - pipeline_exec.start_time) * 1000)

        return {
            "grading_config_id": self._grading_config_id,
            "external_user_id": self._student_name,
            "username": self._student_name,
            "language": self._language,
            "status": status,
            "final_score": final_score,
            "feedback": feedback,
            "result_tree": result_tree_dict,
            "focus": focus_dict,
            "pipeline_execution": None,
            "execution_time_ms": execution_time_ms,
            "error_message": error_message,
            "submission_metadata": self._get_github_context(),
        }

    def _build_minimal_payload(
        self, user_id: str, score: float, feedback: Optional[str]
    ) -> dict:
        """Build a minimal valid payload when no pipeline execution context is available."""
        return {
            "grading_config_id": self._grading_config_id,
            "external_user_id": user_id,
            "username": user_id,
            "language": self._language,
            "status": "completed",
            "final_score": score,
            "feedback": feedback,
            "result_tree": None,
            "focus": None,
            "pipeline_execution": None,
            "execution_time_ms": 0,
            "error_message": None,
            "submission_metadata": self._get_github_context(),
        }

    @staticmethod
    def _get_github_context() -> dict:
        """Read GitHub Actions runtime environment variables."""
        return {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "commit_sha": os.getenv("GITHUB_SHA"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "actor": os.getenv("GITHUB_ACTOR"),
            "ref": os.getenv("GITHUB_REF"),
        }
