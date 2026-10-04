"""Version/discriminant and timestamp encodings match the published wire schema."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from autograder.models.contracts.outcome import validate_outcome, outcome_json_schema


def failure():
    return {
        "schema_version": "1.0",
        "status": "failed",
        "execution_id": "wire-check",
        "language": "python",
        "provenance": {"definition_hash": "0" * 64},
        "started_at": "2026-10-04T12:00:00Z",
        "finished_at": "2026-10-04T12:00:01Z",
        "duration_ms": 1000,
        "error": {
            "code": "EXECUTION_ERROR",
            "message": "Execution failed.",
            "category": "internal",
            "retryable": False,
            "correlation_id": "wire-check",
        },
    }


@pytest.mark.parametrize("field", ["schema_version", "status"])
def test_wire_requires_explicit_version_and_discriminant(field):
    value = failure()
    value.pop(field)
    with pytest.raises(ValidationError):
        validate_outcome(value)
    schema = outcome_json_schema()
    for status in ("CompletedOutcome", "FailedOutcome"):
        assert field in schema["$defs"][status]["required"]


@pytest.mark.parametrize(
    "started,finished",
    [
        (0, 1),
        ("0", "1"),
        (True, True),
        ("2026-10-04 12:00:00+00:00", "2026-10-04 12:00:01+00:00"),
        ("2026-10-04T12:00:00", "2026-10-04T12:00:01"),
        ("2026-10-04", "2026-10-04"),
    ],
)
def test_wire_rejects_non_rfc3339_timestamps(started, finished):
    value = failure()
    value.update(started_at=started, finished_at=finished)
    with pytest.raises(ValidationError):
        validate_outcome(value)


def test_offset_normalization_and_python_datetime_are_supported():
    value = failure()
    value.update(
        started_at="2026-10-04T09:00:00-03:00", finished_at="2026-10-04T09:00:01-03:00"
    )
    normalized = validate_outcome(value)
    assert normalized.started_at == datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    assert normalized.model_dump(mode="json")["started_at"] == "2026-10-04T12:00:00Z"
    python_value = normalized.model_dump()
    assert validate_outcome(python_value).model_dump(
        mode="json"
    ) == normalized.model_dump(mode="json")
