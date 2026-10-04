"""Publication consumes the exact terminal contract, never a mutable pipeline."""
from unittest.mock import MagicMock

from github_action.cloud_exporter import CloudPublisher


def test_publisher_preserves_exact_outcome_and_has_no_engine_dependency():
    client, definition, outcome = MagicMock(), MagicMock(), MagicMock()
    definition.model_dump.return_value = {"schema_version": "1.0"}
    value = {"status": "completed", "score": 100, "tree": {"base": {}},
             "comparison": {"status": "completed", "content": {"score_delta": 5}}}
    outcome.model_dump.return_value = value
    outcome.language = "python"
    publisher = CloudPublisher(client, 7, definition)
    payload = publisher.payload(outcome, "alice")
    assert payload["outcome"] == value
    assert payload["definition_snapshot"] == {"schema_version": "1.0"}
    assert payload["external_user_id"] == "alice"
    publisher.publish(payload)
    publisher.publish(payload)
    assert client.submit_external_result.call_count == 2
    outcome.get_grade_step_result.assert_not_called()
