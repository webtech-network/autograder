"""Revision 011 stores every definition the API still grades in format 2.0 (ONB-07).

A database at revision 010 holds what the 1.0 release wrote: an active
configuration with a 1.0 snapshot, one that is no longer valid, a finished
submission whose outcome is bound to the 1.0 snapshot, and a queued submission.
The documented ``alembic upgrade head`` runs as a subprocess on SQLite and on
PostgreSQL; the upgraded host then serves, compares and accepts work through
its real HTTP routes, and the downgrade refuses to hand 2.0 data back.
"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

from httpx import AsyncClient, ASGITransport
import pytest
import sqlalchemy as sa

from autograder import Submission, SubmissionFile, build_pipeline, compile_snapshot
from autograder.models.contracts.definition import snapshot_hash
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.language import Language
from autograder.services.definition_migration import convert_snapshot
from tests.builtin_evaluator_cases import GOOD, BAD
from tests.web.test_migrations import TOKEN, alembic, on_database, postgres_url, run, started_host  # pylint: disable=unused-import

CORPUS = json.loads((Path(__file__).resolve().parents[1] / "definition_v1_corpus.json").read_text(encoding="utf-8"))
#: A 1.0 snapshot exactly as the 1.0 release stored it, and the hash recorded with it.
V1 = CORPUS["tests/builtin_evaluator_cases.py:DEFINITION"]["snapshot"]
V1_HASH = CORPUS["tests/builtin_evaluator_cases.py:DEFINITION"]["definition_hash"]
FILES = {name: {"filename": name, "content": content, "changed_lines": None, "file_metadata": None}
         for name, content in BAD.items()}


def invalid_today():
    """A 1.0 snapshot that ONB-01 made invalid: an explicit presence threshold of 0."""
    value = deepcopy(V1)
    value["criteria"]["base"]["subjects"][0]["tests"][0]["parameters"]["required_count"] = 0
    return value


def graded(files, provenance):
    """A real outcome of the converted rubric, bound to ``provenance``."""
    compiled = compile_snapshot(convert_snapshot(V1).definition)
    submission = Submission("student", "student", "web", {name: SubmissionFile(name, content)
                                                         for name, content in files.items()},
                            language=Language.NODE)
    outcome = build_pipeline(definition=compiled).run(submission).outcome.model_dump(mode="json")
    return {**outcome, "provenance": provenance}


def seed(connection):
    tables = sa.MetaData()
    tables.reflect(connection)
    configurations, submissions, results = (tables.tables[name] for name in
                                            ("grading_configurations", "submissions", "submission_results"))
    connection.execute(configurations.insert(), [
        {"id": 1, "external_assignment_id": "web", "version": 1, "is_active": True,
         "definition": V1, "definition_hash": V1_HASH},
        {"id": 2, "external_assignment_id": "broken", "version": 3, "is_active": True,
         "definition": invalid_today(), "definition_hash": snapshot_hash(invalid_today())},
        {"id": 3, "external_assignment_id": "legacy", "version": 1, "is_active": False,
         "definition": None, "definition_hash": None},
    ])
    common = {"grading_config_id": 1, "external_user_id": "student", "username": "Student",
              "submission_files": FILES, "language": "node", "locale": "en", "attempt_count": 0,
              "definition_snapshot": V1, "definition_hash": V1_HASH, "configuration_version": 1}
    connection.execute(submissions.insert(), [{"id": 1, "status": "completed", **common},
                                              {"id": 2, "status": "pending", **common},
                                              {"id": 3, "status": "pending", **common,
                                               "grading_config_id": 2}])
    connection.execute(submissions.update().where(submissions.c.id == 3).values(
        definition_snapshot=invalid_today(), definition_hash=snapshot_hash(invalid_today())))
    outcome = graded(BAD, {"schema_version": "1.0", "definition_hash": V1_HASH, "reference": "1", "revision": 1})
    connection.execute(results.insert(), [{"submission_id": 1, "final_score": outcome["score"], "outcome": outcome,
                                           "execution_time_ms": 5, "pipeline_status": "success"}])
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SELECT setval('grading_configurations_id_seq', 3), "
                                   "setval('submissions_id_seq', 3)"))


def stored(connection):
    rows = connection.execute(sa.text("SELECT id, status, definition_snapshot, definition_hash FROM submissions "
                                      "ORDER BY id")).all()
    return {row.id: (row.status, row.definition_snapshot, row.definition_hash) for row in rows}


def as_json(value):
    return json.loads(value) if isinstance(value, str) else value


async def upgraded_database_serves_history_and_new_work(url, tmp_path):
    alembic(url, "upgrade", "010")
    await on_database(url, seed)
    before = await on_database(url, stored)
    upgrade = alembic(url, "upgrade", "head")
    assert "grading_configurations.id=2 quarantined" in upgrade.stderr
    assert "every HTML and CSS file" in upgrade.stderr  # the converter's note, per stored definition
    after = await on_database(url, stored)
    converted = convert_snapshot(V1).definition
    current = compile_snapshot(converted)
    # Finished work keeps its 1.0 snapshot and hash; queued work is rebound to the converted snapshot.
    assert after[1] == before[1]
    assert (as_json(after[2][1]), after[2][2]) == (converted, current.definition_hash)
    assert after[3] == before[3]  # does not convert: left to fail as it would have
    alembic(url, "upgrade", "head")  # running it again changes nothing
    assert await on_database(url, stored) == after

    app = await started_host(url, tmp_path)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {TOKEN}"}) as client:
            web = (await client.get("/api/v1/configs/web")).json()
            assert (web["version"], web["definition"], web["definition_hash"], web["is_active"]) == (
                2, converted, current.definition_hash, True)
            broken = (await client.get("/api/v1/configs/broken")).json()
            assert (broken["version"], broken["is_active"], broken["definition"], broken["definition_hash"]) == (
                4, False, None, None)
            assert broken["migration_error"]["definition"] == invalid_today()
            assert broken["migration_error"]["errors"][0]["path"][-1] == "required_count"
            legacy = (await client.get("/api/v1/configs/legacy")).json()
            assert (legacy["version"], legacy["definition"]) == (1, None)

            details = (await client.get("/api/v1/submissions/1/details")).json()
            assert details["definition_snapshot"] == V1 and details["provenance_status"] == "bound_snapshot"
            assert details["outcome"]["provenance"]["schema_version"] == "1.0"
            assert snapshot_hash(details["definition_snapshot"]) == details["outcome"]["provenance"]["definition_hash"]

            # New work: an attested outcome at the converted revision, compared with the 1.0 baseline.
            head = graded(GOOD, DefinitionProvenance(definition_hash=current.definition_hash, reference="1",
                                                     revision=2).model_dump(mode="json"))
            attested = await client.post("/api/v1/submissions/external-results", json={
                "grading_config_id": 1, "external_user_id": "student", "username": "Student",
                "language": "node", "definition_snapshot": converted, "outcome": head})
            assert attested.status_code == 200, attested.text
            comparison = await client.get(f"/api/v1/submissions/{attested.json()['submission_id']}/comparison",
                                          params={"baseline_submission_id": 1})
            assert comparison.status_code == 200, comparison.text
            body = comparison.json()
            assert (body["compatibility"], body["changed_definition_sections"]) == ("cross_revision",
                                                                                    ["schema_version"])
            assert {row["status"] for row in body["criteria"]} <= {"improved", "regressed", "unchanged"}
            assert body["baseline"]["score"] == details["outcome"]["score"] < body["head"]["score"]
            accepted = await client.post("/api/v1/submissions", json={
                "external_assignment_id": "web", "external_user_id": "student", "username": "Student",
                "files": [{"filename": name, "content": content} for name, content in GOOD.items()]})
            assert accepted.status_code == 202, accepted.text
    finally:
        await app.state.host.close()

    downgrade = run(url, "-m", "alembic", "-c", "web/alembic.ini", "downgrade", "010")
    assert downgrade.returncode != 0
    assert "restoring the database backup" in downgrade.stderr


def test_sqlite_database_at_010_upgrades_its_definitions_to_format_2(tmp_path):
    asyncio.run(upgraded_database_serves_history_and_new_work(
        f"sqlite+aiosqlite:///{tmp_path / 'upgraded.sqlite3'}", tmp_path))


async def test_postgres_database_at_010_upgrades_its_definitions_to_format_2(postgres_url, tmp_path):
    await upgraded_database_serves_history_and_new_work(await postgres_url(), tmp_path)


def test_empty_database_downgrades_through_011(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'empty.sqlite3'}"
    alembic(url, "upgrade", "head")
    alembic(url, "downgrade", "010")
