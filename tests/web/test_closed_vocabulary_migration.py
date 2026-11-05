"""Revision 010 binds stored locales and outcome codes to the closed vocabularies (COR-07).

The migration runs against plain SQL tables, not the ORM models, exactly as it
meets rows written by earlier releases.
"""
import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _closed_vocabulary_tables(connection):
    metadata = sa.MetaData()
    submissions = sa.Table("submissions", metadata, sa.Column("id", sa.Integer, primary_key=True),
                           sa.Column("locale", sa.String(32), nullable=False))
    results = sa.Table("submission_results", metadata, sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("outcome", sa.JSON, nullable=True))
    metadata.create_all(connection)
    return submissions, results


def _failed(code, execution_id="legacy"):
    return {"schema_version": "1.0", "status": "failed", "execution_id": execution_id, "language": "python",
            "provenance": {"schema_version": "1.0", "definition_hash": "a" * 64},
            "started_at": "2026-10-04T12:00:00Z", "finished_at": "2026-10-04T12:00:01Z", "duration_ms": 1000,
            "score": None, "tree": None, "feedback": {"status": "disabled"}, "comparison": {"status": "disabled"},
            "error": {"code": code, "message": "Grading execution could not be completed.", "category": "internal",
                      "retryable": False, "correlation_id": execution_id}}


def _upgrade_010(connection, monkeypatch):
    migration = importlib.import_module("web.migrations.versions.010_closed_vocabularies")
    monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
    migration.upgrade()


def test_closed_vocabulary_migration_binds_stored_locales_and_codes(monkeypatch):
    from autograder.models.contracts.outcome import validate_outcome
    from tests.locale_cases import ACCEPTED, REJECTED
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        submissions, results = _closed_vocabulary_tables(connection)
        stored = [value for value, _ in ACCEPTED] + [value for value in REJECTED if len(value) <= 32]
        connection.execute(submissions.insert(), [{"id": i, "locale": value} for i, value in enumerate(stored)])
        kept = _failed("PROVIDER_ERROR", "kept")
        connection.execute(results.insert(), [{"id": 1, "outcome": _failed("EXECUTION_FAILED")},
                                              {"id": 2, "outcome": kept}, {"id": 3, "outcome": None}])
        _upgrade_010(connection, monkeypatch)
        locales = [row.locale for row in connection.execute(sa.select(submissions).order_by(submissions.c.id))]
        # Unsupported values were rendered in English by the old fallback; that is what they received.
        assert locales == [canonical for _, canonical in ACCEPTED] + ["en"] * (len(stored) - len(ACCEPTED))
        outcomes = [row.outcome for row in connection.execute(sa.select(results).order_by(results.c.id))]
        assert outcomes[0]["error"]["code"] == "EXECUTION_ERROR"
        assert outcomes[0]["error"]["message"] == "The grading execution could not complete."
        assert outcomes[1:] == [kept, None]
        validate_outcome(outcomes[0])
        # Idempotent: a second run changes nothing.
        _upgrade_010(connection, monkeypatch)
        assert [row.outcome for row in connection.execute(sa.select(results).order_by(results.c.id))] == outcomes


def test_closed_vocabulary_migration_refuses_unpublished_codes(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with pytest.raises(RuntimeError, match=r"\{7: \['CUSTOM_CODE'\]\}"):
        with engine.begin() as connection:
            _, results = _closed_vocabulary_tables(connection)
            connection.execute(results.insert(), [{"id": 7, "outcome": _failed("CUSTOM_CODE")}])
            _upgrade_010(connection, monkeypatch)
