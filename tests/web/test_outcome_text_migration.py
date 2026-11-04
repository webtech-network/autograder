"""Outcomes stored before COR-06 still serve, compare and deliver (migration evidence).

Before the text bounds, any flooded I/O failure stored a report of up to about
1 MiB. These tests write exactly that shape (bypassing today's producer), then
run the real Alembic revision against the app's database and the real receipt
reader, and check the result through the real ASGI app.
"""
import importlib
import json
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.exceptions import ResponseValidationError

from autograder.models.contracts.outcome import (
    MAX_FEEDBACK_BYTES, MAX_REPORT_BYTES, bound_outcome_text, bound_text, validate_outcome,
)
from tests.web.test_contracts_v1 import create, integration_auth  # noqa: F401  # pylint: disable=unused-import  # autouse token
from tests.web.test_submission_comparison import attest, bound, compare
from web.service.outcome_delivery import republish_receipt

MIGRATION = "web.migrations.versions.008_bound_outcome_text"
MARKER = re.compile(r"\n\[\.\.\. (\d+) of (\d+) bytes omitted \.\.\.\]\n")
# What a pre-COR-06 flood stored: a whole 1 MiB-class stream, with multibyte text.
LEGACY_REPORT = "FAILURE: Output Mismatch.\nActual: '" + "o" * 999_000 + "é" * 500 + "'"
LEGACY_FEEDBACK = "# Feedback\n" + "😀" * 100_000


def legacy(outcome):
    outcome = json.loads(json.dumps(outcome))
    outcome["tree"]["base"]["tests"][0]["report"] = LEGACY_REPORT
    outcome["feedback"] = {"status": "completed", "content": LEGACY_FEEDBACK, "error": None}
    return outcome


def sync_engine(db_engine):
    return sa.create_engine(db_engine.url.set(drivername="sqlite"))


RESULTS = sa.table("submission_results", sa.column("submission_id", sa.Integer), sa.column("outcome", sa.JSON))


def stored_outcomes(engine):
    with engine.connect() as connection:
        return dict(connection.execute(sa.select(RESULTS.c.submission_id, RESULTS.c.outcome)).all())


def store(engine, submission_id, outcome):
    with engine.begin() as connection:
        connection.execute(RESULTS.update().where(RESULTS.c.submission_id == submission_id).values(outcome=outcome))


def upgrade(engine, monkeypatch):
    migration = importlib.import_module(MIGRATION)
    with engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()


def assert_excerpt(text, original, limit):
    assert len(text.encode("utf-8")) <= limit
    [(omitted, total)] = MARKER.findall(text)
    assert int(total) == len(original.encode("utf-8"))
    head, tail = MARKER.split(text)[0], MARKER.split(text)[-1]
    assert original.startswith(head) and original.endswith(tail)
    assert len(head.encode()) + len(tail.encode()) + int(omitted) == int(total)


@pytest.mark.asyncio
async def test_stored_pre_bound_outcomes_serve_and_compare_after_the_migration(
        test_client, db_engine, monkeypatch):
    config = await create(test_client)
    baseline = await attest(test_client, config, {"hello": 0})
    head = await attest(test_client, config, {"hello": 100})
    engine = sync_engine(db_engine)
    try:
        store(engine, baseline, legacy(stored_outcomes(engine)[baseline]))
        untouched = stored_outcomes(engine)[head]
        # The older row reproduces the reported failure before the upgrade.
        with pytest.raises(ResponseValidationError, match="text_too_large"):
            await test_client.get(f"/api/v1/submissions/{baseline}/details")
        assert (await compare(test_client, head, baseline)).status_code == 409

        upgrade(engine, monkeypatch)
        migrated = stored_outcomes(engine)
        upgrade(engine, monkeypatch)
        assert stored_outcomes(engine) == migrated  # idempotent
    finally:
        engine.dispose()

    assert migrated[head] == untouched  # text within the bounds is not rewritten
    details = await test_client.get(f"/api/v1/submissions/{baseline}/details")
    assert details.status_code == 200, details.text[:2000]
    outcome = details.json()["outcome"]
    assert outcome["score"] == 0 and outcome["tree"]["base"]["tests"][0]["score"] == 0
    assert_excerpt(outcome["tree"]["base"]["tests"][0]["report"], LEGACY_REPORT, MAX_REPORT_BYTES)
    assert outcome["feedback"]["status"] == "completed"
    assert_excerpt(outcome["feedback"]["content"], LEGACY_FEEDBACK, MAX_FEEDBACK_BYTES)
    # The stored excerpt is exactly what the engine would produce today.
    assert outcome["tree"]["base"]["tests"][0]["report"] == bound_text(LEGACY_REPORT, MAX_REPORT_BYTES)

    comparison = await compare(test_client, head, baseline)
    assert comparison.status_code == 200, comparison.text
    assert (comparison.json()["score_delta"], comparison.json()["improved"]) == (100, True)


def test_migration_pages_through_null_failed_and_legacy_rows(monkeypatch):
    engine = sa.create_engine("sqlite://")
    results = sa.Table("submission_results", sa.MetaData(), sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("outcome", sa.JSON, nullable=True))
    results.metadata.create_all(engine)
    from autograder.models.contracts.definition import compile_definition
    from tests.unit.models.test_outcome_comparison import build_outcome
    from tests.web.test_contracts_v1 import definition
    compiled = compile_definition(definition())
    completed = build_outcome(compiled, {"hello": 50}).model_dump(mode="json")
    failed = build_outcome(compiled, {}, failed=True).model_dump(mode="json")
    rows = [None, failed, legacy(completed), completed, legacy(completed)]
    with engine.begin() as connection:
        connection.execute(results.insert(), [{"id": index + 1, "outcome": row} for index, row in enumerate(rows)])
    monkeypatch.setattr(importlib.import_module(MIGRATION), "_PAGE", 2)  # several pages, one partial
    upgrade(engine, monkeypatch)
    with engine.connect() as connection:
        after = [row for (row,) in connection.execute(sa.select(results.c.outcome).order_by(results.c.id))]
    engine.dispose()
    assert after[:2] == [None, failed] and after[3] == completed
    for row in (after[2], after[4]):
        assert validate_outcome(row).score == 50
        assert row == bound_outcome_text(legacy(completed)) != legacy(completed)


@pytest.mark.asyncio
async def test_receipt_written_before_the_bounds_still_delivers(test_client, application):
    config = await create(test_client)
    response = await test_client.post("/api/v1/submissions", json={
        "external_assignment_id": "assignment", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "main.py", "content": "print('Hello')"}]})
    assert response.status_code == 202, response.text
    host = application.state.host
    request, attempt_id = await host.worker.claim()
    outcome = legacy(bound(config, {"hello": 0}, execution_id=f"local-{request.submission_id}"))
    # Byte-for-byte what write_receipt fsynced before the bounds existed.
    receipt = {"submission_id": request.submission_id, "attempt_id": attempt_id, "outcome": outcome}
    directory = Path(host.settings.RECEIPT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"submission-{request.submission_id}-{name}.json" for name in ("first", "retry")]
    for path in paths:
        path.write_text(json.dumps(receipt), encoding="utf-8")

    await republish_receipt(paths[0], host.sessions)
    # A second copy of the same receipt equals the stored (excerpted) row.
    await republish_receipt(paths[1], host.sessions)
    assert not any(path.exists() for path in paths)

    details = await test_client.get(f"/api/v1/submissions/{request.submission_id}/details")
    assert details.status_code == 200, details.text[:2000]
    assert details.json()["outcome"] == bound_outcome_text(outcome)
    assert_excerpt(details.json()["outcome"]["tree"]["base"]["tests"][0]["report"], LEGACY_REPORT, MAX_REPORT_BYTES)
