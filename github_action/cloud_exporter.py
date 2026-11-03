"""Publish a finished outcome without accessing mutable execution state."""
import os


class CloudPublisher:
    def __init__(self, client, grading_config_id, definition):
        self.client = client
        self.grading_config_id = grading_config_id
        self.definition = definition

    def payload(self, outcome, user_name):
        return {
            "grading_config_id": self.grading_config_id,
            "definition_snapshot": self.definition.model_dump(mode="json"),
            "external_user_id": user_name,
            "username": user_name,
            "language": outcome.language,
            "outcome": outcome.model_dump(mode="json"),
            "submission_metadata": {
                "repository": os.getenv("GITHUB_REPOSITORY"),
                "commit_sha": os.getenv("GITHUB_SHA"),
                "run_id": os.getenv("GITHUB_RUN_ID"),
                "actor": os.getenv("GITHUB_ACTOR"),
                "ref": os.getenv("GITHUB_REF"),
            },
        }

    def publish(self, payload):
        # The same saved payload may be explicitly retried without rerunning grading.
        return self.client.submit_external_result(payload, idempotency_key=delivery_key(payload))


def delivery_key(payload):
    """One grading execution is one attestation operation (INT-04).

    The key derives from the saved outcome, so retrying delivery.json (even one
    written before keys existed) reuses it, while a new workflow attempt grades
    again and receives a new execution ID and key.
    """
    return "action-outcome:" + payload["outcome"]["execution_id"]
