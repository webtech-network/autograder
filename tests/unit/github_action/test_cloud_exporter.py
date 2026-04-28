# pylint: disable=protected-access
"""Unit tests for github_action.cloud_exporter.CloudExporter."""

import os
import time
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from github_action.cloud_client import CloudClient
from github_action.cloud_exporter import CloudExporter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> CloudClient:
    client = MagicMock(spec=CloudClient)
    client.submit_external_result.return_value = {}
    return client

def _make_exporter(
    config_id: int = 42,
    language: str = "python",
    student_name: str = "student1",
) -> tuple[CloudExporter, CloudClient]:
    client = _make_client()
    exporter = CloudExporter(client, config_id, language, student_name)
    return exporter, client

def _make_pipeline_exec(
    *,
    user_id: str = "student1",
    final_score: float = 85.0,
    feedback: Optional[str] = "Good job!",
    status_value: str = "success",
    start_time: Optional[float] = None,
    include_focus: bool = True,
    include_result_tree: bool = True,
) -> MagicMock:
    """Build a minimal mock PipelineExecution for exporter tests."""
    pe = MagicMock()
    pe.submission.user_id = user_id
    pe.status.value = status_value
    pe.start_time = start_time if start_time is not None else time.time() - 1.5

    # Grade step
    grade_result = MagicMock()
    grade_result.final_score = final_score
    pe.get_grade_step_result.return_value = grade_result

    # Feedback
    pe.get_feedback.return_value = feedback

    # Result tree
    if include_result_tree:
        result_tree = MagicMock()
        result_tree.to_dict.return_value = {"final_score": final_score, "tree": {}}
        pe.get_result_tree.return_value = result_tree
    else:
        pe.get_result_tree.side_effect = ValueError("No grade result")

    # Focus
    if include_focus:
        focus = MagicMock()
        focus.to_dict.return_value = {"base": [], "penalty": None, "bonus": None}
        pe.get_focus.return_value = focus
    else:
        pe.get_focus.side_effect = ValueError("No focus")

    return pe

# GitHub env vars injected by every test in this module
_GITHUB_ENV = {
    "GITHUB_REPOSITORY": "owner/repo",
    "GITHUB_SHA": "abc123def456",
    "GITHUB_RUN_ID": "9876543210",
    "GITHUB_ACTOR": "student1",
    "GITHUB_REF": "refs/heads/main",
}

# ---------------------------------------------------------------------------
# export_with_context — payload structure
# ---------------------------------------------------------------------------

class TestExportWithContextPayloadStructure:
    def test_submits_to_cloud_client(self):
        """Asserts submit_external_result is called once."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        client.submit_external_result.assert_called_once()

    def test_score_in_payload(self):
        """Asserts the final score is present in the submitted payload."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(final_score=92.5)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["final_score"] == 92.5

    def test_feedback_in_payload(self):
        """Asserts the feedback string is present in the submitted payload."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(feedback="Excellent work!")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["feedback"] == "Excellent work!"

    def test_none_feedback_in_payload(self):
        """Asserts None feedback is preserved in the payload."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(feedback=None)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["feedback"] is None

    def test_status_in_payload(self):
        """Asserts the payload status is 'completed' when grading succeeds."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(status_value="success")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["status"] == "completed"

    def test_grading_config_id_in_payload(self):
        """Asserts the integer grading config ID is included for server-side correlation."""
        exporter, client = _make_exporter(config_id=99)
        pe = _make_pipeline_exec()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["grading_config_id"] == 99
        assert isinstance(payload["grading_config_id"], int)

    def test_result_tree_serialised_in_payload(self):
        """Asserts the result tree to_dict() output is included in the payload."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(include_result_tree=True)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["result_tree"] is not None
        assert "final_score" in payload["result_tree"]

    def test_focus_serialised_in_payload(self):
        """Asserts the focus dict is included in the payload."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(include_focus=True)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["focus"] is not None
        assert "base" in payload["focus"]

    def test_execution_time_ms_positive(self):
        """Asserts execution_time_ms is a positive integer."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(start_time=time.time() - 2.0)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert isinstance(payload["execution_time_ms"], int)
        assert payload["execution_time_ms"] > 0

    def test_submission_user_id_in_payload(self):
        """Asserts external_user_id and username are set from the student_name."""
        exporter, client = _make_exporter(student_name="alice")
        pe = _make_pipeline_exec(user_id="alice")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["external_user_id"] == "alice"
        assert payload["username"] == "alice"

    def test_error_message_none_on_success(self):
        """Asserts error_message is None when the pipeline succeeds."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["error_message"] is None

# ---------------------------------------------------------------------------
# export_with_context — GitHub context mapping
# ---------------------------------------------------------------------------

class TestGitHubContextMapping:
    def test_all_github_env_vars_present_in_payload(self):
        """Asserts all five GitHub context fields are present in submission_metadata."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec()

        with patch.dict(os.environ, _GITHUB_ENV, clear=False):
            exporter.export_with_context(pe)

        github_ctx = client.submit_external_result.call_args[0][0]["submission_metadata"]
        assert github_ctx["repository"] == "owner/repo"
        assert github_ctx["commit_sha"] == "abc123def456"
        assert github_ctx["run_id"] == "9876543210"
        assert github_ctx["actor"] == "student1"
        assert github_ctx["ref"] == "refs/heads/main"

    def test_missing_github_env_vars_default_to_none(self):
        """Asserts missing GitHub env vars produce None values (not KeyError)."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec()

        # Remove all GitHub env vars
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GITHUB_")
        }
        with patch.dict(os.environ, clean_env, clear=True):
            exporter.export_with_context(pe)

        github_ctx = client.submit_external_result.call_args[0][0]["submission_metadata"]
        assert github_ctx["repository"] is None
        assert github_ctx["commit_sha"] is None
        assert github_ctx["run_id"] is None
        assert github_ctx["actor"] is None
        assert github_ctx["ref"] is None

# ---------------------------------------------------------------------------
# export_with_context — graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_result_tree_none_when_grade_step_unavailable(self):
        """Asserts result_tree is None in the payload when get_result_tree raises."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(include_result_tree=False)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["result_tree"] is None

    def test_focus_none_when_focus_unavailable(self):
        """Asserts focus is None in the payload when get_focus raises."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec(include_focus=False)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["focus"] is None

    def test_score_zero_and_error_message_set_when_grade_result_raises(self):
        """Asserts score defaults to 0 and error_message is set when get_grade_step_result raises."""
        exporter, client = _make_exporter()
        pe = _make_pipeline_exec()
        pe.get_grade_step_result.side_effect = ValueError("Grade step not run")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export_with_context(pe)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["final_score"] == 0.0
        assert payload["error_message"] is not None
        assert "Grade step not run" in payload["error_message"]
        assert payload["status"] == "failed"

# ---------------------------------------------------------------------------
# export (minimal / fallback path)
# ---------------------------------------------------------------------------

class TestMinimalExport:
    def test_submits_score_and_feedback(self):
        """Asserts minimal export passes score and feedback to the cloud client."""
        exporter, client = _make_exporter()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export("student1", 70.0, "Decent effort.")

        payload = client.submit_external_result.call_args[0][0]
        assert payload["final_score"] == 70.0
        assert payload["feedback"] == "Decent effort."

    def test_result_tree_and_focus_are_none(self):
        """Asserts result_tree and focus are None in the minimal payload."""
        exporter, client = _make_exporter()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export("student1", 50.0)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["result_tree"] is None
        assert payload["focus"] is None

    def test_execution_time_ms_is_zero(self):
        """Asserts execution_time_ms is 0 in the minimal payload (no pipeline context)."""
        exporter, client = _make_exporter()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export("student1", 50.0)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["execution_time_ms"] == 0

    def test_config_id_present(self):
        """Asserts the integer grading config ID is included even in the minimal payload."""
        exporter, client = _make_exporter(config_id=42)

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export("student1", 88.0)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["grading_config_id"] == 42

    def test_none_feedback_handled(self):
        """Asserts None feedback is preserved in the minimal payload."""
        exporter, client = _make_exporter()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.export("student1", 80.0, None)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["feedback"] is None

# ---------------------------------------------------------------------------
# Exporter ABC integration
# ---------------------------------------------------------------------------

class TestExporterAbcIntegration:
    def test_is_instance_of_exporter_abc(self):
        """Asserts CloudExporter satisfies the Exporter ABC."""
        from autograder.models.abstract.exporter import Exporter

        exporter, _ = _make_exporter()
        assert isinstance(exporter, Exporter)

    def test_export_with_context_default_calls_export_on_base_exporter(self):
        """Asserts the default export_with_context on Exporter ABC delegates to export()."""
        from autograder.models.abstract.exporter import Exporter

        class MinimalExporter(Exporter):
            def __init__(self):
                self.calls = []

            def export(self, user_id, score, feedback=None):
                self.calls.append((user_id, score, feedback))

        minimal = MinimalExporter()
        pe = _make_pipeline_exec(user_id="bob", final_score=55.0, feedback="Try again.")
        minimal.export_with_context(pe)

        assert minimal.calls == [("bob", 55.0, "Try again.")]

# ---------------------------------------------------------------------------
# submit_failure
# ---------------------------------------------------------------------------

class TestSubmitFailure:
    def test_submit_failure_calls_client(self):
        """Asserts submit_failure calls submit_external_result once."""
        exporter, client = _make_exporter(config_id=7, language="java", student_name="alice")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.submit_failure("sandbox timeout", 5000)

        client.submit_external_result.assert_called_once()

    def test_submit_failure_payload_fields(self):
        """Asserts submit_failure builds the correct payload fields."""
        exporter, client = _make_exporter(config_id=7, language="java", student_name="alice")

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.submit_failure("sandbox timeout", 5000)

        payload = client.submit_external_result.call_args[0][0]
        assert payload["grading_config_id"] == 7
        assert payload["external_user_id"] == "alice"
        assert payload["username"] == "alice"
        assert payload["language"] == "java"
        assert payload["status"] == "failed"
        assert payload["final_score"] == 0.0
        assert payload["execution_time_ms"] == 5000
        assert payload["error_message"] == "sandbox timeout"

    def test_submit_failure_default_execution_time(self):
        """Asserts submit_failure defaults execution_time_ms to 0."""
        exporter, client = _make_exporter()

        with patch.dict(os.environ, _GITHUB_ENV):
            exporter.submit_failure("some error")

        payload = client.submit_external_result.call_args[0][0]
        assert payload["execution_time_ms"] == 0
