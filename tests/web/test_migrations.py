"""Migrations are the only schema owner, verified on a real database.

PostgreSQL tests need TEST_POSTGRES_URL (a role allowed to create databases);
each test creates and drops its own database. The migration command runs as the
documented subprocess, exactly as operators, Compose and deployment run it.
"""
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from httpx import AsyncClient, ASGITransport
import pytest
from sqlalchemy import Column, Integer, MetaData, inspect, make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from autograder.models.capabilities import HostCapabilities
from web.core.config import Settings
from web.database.base import Base
from web.database.schema import SchemaNotCurrent, adopt, head_revision, schema_differences
from web.main import create_app
from tests.web.test_contracts_v1 import definition


REPO = Path(__file__).resolve().parents[2]
LEGACY_007 = Path(__file__).parent / "fixtures" / "legacy_007_schema.sql"
TOKEN = "migration-test-token"


def run(url, *args):
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(REPO)}
    return subprocess.run([sys.executable, *args], cwd=REPO, env=env, capture_output=True, text=True,
                          timeout=120, check=False)


def alembic(url, *args):
    process = run(url, "-m", "alembic", "-c", "web/alembic.ini", *args)
    assert process.returncode == 0, process.stderr
    return process


async def on_database(url, function):
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            return await connection.run_sync(function)
    finally:
        await engine.dispose()


def current_revision(connection):
    tables = inspect(connection).get_table_names()
    if "alembic_version" not in tables:
        return None
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def fingerprint(connection):
    """Every PostgreSQL schema property the application depends on, in a stable order."""
    queries = {
        "columns": """SELECT table_name, column_name, ordinal_position, data_type, character_maximum_length,
                      is_nullable, column_default FROM information_schema.columns
                      WHERE table_schema = 'public' ORDER BY table_name, ordinal_position""",
        "indexes": "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY indexname",
        "constraints": """SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint
                          WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2""",
        "enums": """SELECT t.typname, e.enumsortorder, e.enumlabel FROM pg_type t JOIN pg_enum e
                    ON e.enumtypid = t.oid ORDER BY 1, 2""",
    }
    return {name: [tuple(row) for row in connection.execute(text(query))] for name, query in queries.items()}


@pytest.fixture
async def postgres_url():
    """Return a factory of empty, disposable PostgreSQL databases."""
    admin_url = os.getenv("TEST_POSTGRES_URL")
    if not admin_url:
        pytest.fail("TEST_POSTGRES_URL is required for the PostgreSQL tier (make test-postgres)", pytrace=False)
    created = []

    async def create():
        name = "test_migrations_" + uuid4().hex
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin.connect() as connection:
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
        finally:
            await admin.dispose()
        created.append(name)
        return make_url(admin_url).set(database=name).render_as_string(hide_password=False)

    yield create

    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            for name in created:
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await admin.dispose()


async def load_legacy_007(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            raw = await connection.get_raw_connection()
            await raw.driver_connection.execute(LEGACY_007.read_text())
    finally:
        await engine.dispose()


async def started_host(url, receipts):
    app = create_app(Settings(DATABASE_URL=url, INTEGRATION_TOKEN=TOKEN, RECEIPT_DIR=str(receipts)),
                     capabilities=HostCapabilities(), start_workers=False)
    try:
        await app.state.host.start()
    except BaseException:
        await app.state.host.close()
        raise
    return app


async def test_empty_postgres_upgrades_to_exactly_the_models(postgres_url):
    url = await postgres_url()
    alembic(url, "upgrade", "head")
    assert await on_database(url, current_revision) == head_revision()
    assert await on_database(url, schema_differences) == []


async def test_downgrade_base_then_upgrade_head_round_trips(postgres_url):
    url = await postgres_url()
    alembic(url, "upgrade", "head")
    migrated = await on_database(url, fingerprint)
    alembic(url, "downgrade", "base")
    emptied = await on_database(url, fingerprint)
    assert {row[0] for row in emptied["columns"]} == {"alembic_version"}
    assert emptied["enums"] == []
    assert await on_database(url, current_revision) is None
    alembic(url, "upgrade", "head")
    assert await on_database(url, fingerprint) == migrated
    assert await on_database(url, schema_differences) == []


def test_sqlite_upgrades_to_the_models_and_round_trips(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'migrated.sqlite3'}"
    alembic(url, "upgrade", "head")
    assert asyncio.run(on_database(url, schema_differences)) == []
    alembic(url, "downgrade", "base")
    alembic(url, "upgrade", "head")
    assert asyncio.run(on_database(url, schema_differences)) == []
    assert asyncio.run(on_database(url, current_revision)) == head_revision()


async def test_model_change_without_a_migration_is_detected(postgres_url):
    url = await postgres_url()
    alembic(url, "upgrade", "head")
    changed = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(changed)
    changed.tables["submissions"].append_column(Column("unmigrated", Integer, nullable=True))
    differences = await on_database(url, lambda connection: schema_differences(connection, changed))
    assert [(kind, table, column.name) for kind, _, table, column in differences] == [
        ("add_column", "submissions", "unmigrated")]


async def test_baseline_007_reproduces_the_pre_squash_chain(postgres_url):
    legacy, baseline = await postgres_url(), await postgres_url()
    await load_legacy_007(legacy)
    alembic(baseline, "upgrade", "007")
    assert await on_database(baseline, fingerprint) == await on_database(legacy, fingerprint)


async def test_database_at_007_upgrades_with_its_data(postgres_url, tmp_path):
    """006 failed unreplayable work and 007 receipts survive; naive timestamps become UTC."""
    url, fresh = await postgres_url(), await postgres_url()
    await load_legacy_007(url)

    def seed(connection):
        connection.execute(text(
            "INSERT INTO grading_configurations (id, external_assignment_id, version, is_active, created_at, "
            "updated_at) VALUES (1, 'legacy', 1, false, '2026-03-01 12:00:00', '2026-03-01 12:00:00')"))
        connection.execute(text(
            "INSERT INTO submissions (id, grading_config_id, external_user_id, username, submission_files, "
            "status, submitted_at, graded_at) VALUES "
            # 006 marked unfinished pre-006 work failed; it has no result and no replayable input.
            "(1, 1, 'student', 'Student', '{}', 'failed', '2026-03-01 12:00:00', NULL), "
            "(2, 1, 'student', 'Student', '{}', 'completed', '2026-03-01 12:00:00', '2026-03-01 12:00:05')"))
        connection.execute(text(
            "INSERT INTO submission_results (submission_id, final_score, execution_time_ms, pipeline_status) "
            "VALUES (2, 80, 5, 'success')"))
        connection.execute(text(
            "INSERT INTO operation_receipts (principal, operation, idempotency_key, fingerprint, submission_id) "
            "VALUES ('integration', 'submission.accept', 'key', 'fingerprint', 2)"))
        connection.execute(text("SELECT setval('grading_configurations_id_seq', 1), setval('submissions_id_seq', 2)"))
    await on_database(url, seed)

    alembic(url, "upgrade", "head")
    alembic(fresh, "upgrade", "head")
    assert await on_database(url, current_revision) == head_revision()
    assert await on_database(url, schema_differences) == []
    assert await on_database(url, fingerprint) == await on_database(fresh, fingerprint)
    rows = await on_database(url, lambda connection: connection.execute(text(
        "SELECT id, status, locale, attempt_count, submitted_at, graded_at FROM submissions ORDER BY id")).all())
    assert [tuple(row) for row in rows] == [
        (1, "failed", "en", 0, datetime(2026, 3, 1, 12, tzinfo=timezone.utc), None),
        (2, "completed", "en", 0, datetime(2026, 3, 1, 12, tzinfo=timezone.utc),
         datetime(2026, 3, 1, 12, 0, 5, tzinfo=timezone.utc))]

    app = await started_host(url, tmp_path)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {TOKEN}"}) as client:
            unfinished, completed = [(await client.get(f"/api/v1/submissions/{id_}")).json() for id_ in (1, 2)]
            # New work is written into the upgraded tables (timezone-aware timestamps included).
            created = await client.post("/api/v1/configs", json={"external_assignment_id": "new",
                                                                  "definition": definition()})
            assert created.status_code == 200, created.text
            patched = await client.patch(f"/api/v1/configs/{created.json()['id']}", json={"is_active": False},
                                         headers={"If-Match": created.headers["ETag"]})
            assert patched.status_code == 200, patched.text
    finally:
        await app.state.host.close()
    assert unfinished["error"]["code"] == "RECOVERY_INPUT_UNAVAILABLE" and unfinished["final_score"] is None
    assert unfinished["submitted_at"].startswith("2026-03-01T12:00:00")
    assert completed["error"] is None and completed["final_score"] == 80
    assert completed["provenance_status"] == "unverified_legacy"
    assert await on_database(url, lambda connection: connection.execute(
        text("SELECT count(*) FROM operation_receipts")).scalar_one()) == 1


async def test_startup_never_creates_tables_on_an_empty_database(postgres_url, tmp_path):
    url = await postgres_url()
    with pytest.raises(SchemaNotCurrent, match="has no migration revision.*upgrade head"):
        await started_host(url, tmp_path)
    assert await on_database(url, lambda connection: inspect(connection).get_table_names()) == []


@pytest.mark.parametrize("revision", ["007", "999_from_a_newer_build"])
async def test_startup_refuses_a_database_at_another_revision(postgres_url, tmp_path, revision):
    url = await postgres_url()
    alembic(url, "upgrade", "head")
    await on_database(url, lambda connection: connection.execute(
        text("UPDATE alembic_version SET version_num = :revision"), {"revision": revision}))
    with pytest.raises(SchemaNotCurrent, match=f"is at revision {revision}; this build requires revision "
                                               f"{head_revision()}.*upgrade head"):
        await started_host(url, tmp_path)


async def test_startup_serves_a_database_at_head(postgres_url, tmp_path):
    url = await postgres_url()
    alembic(url, "upgrade", "head")
    app = await started_host(url, tmp_path)
    try:
        assert app.state.host.ready
    finally:
        await app.state.host.close()


async def create_all(url):
    await on_database(url, Base.metadata.create_all)


async def test_adopting_a_create_all_database_stamps_head(postgres_url, tmp_path):
    url = await postgres_url()
    await create_all(url)
    process = run(url, "-m", "web.database.schema", "adopt")
    assert process.returncode == 0, process.stderr
    assert f"stamped revision {head_revision()}" in process.stdout
    assert await on_database(url, current_revision) == head_revision()
    alembic(url, "upgrade", "head")
    app = await started_host(url, tmp_path)
    await app.state.host.close()


async def test_adoption_refuses_a_schema_that_differs_from_the_models(postgres_url):
    url = await postgres_url()
    await create_all(url)
    await on_database(url, lambda connection: connection.execute(text("ALTER TABLE submissions DROP COLUMN locale")))
    process = run(url, "-m", "web.database.schema", "adopt")
    assert process.returncode == 1
    assert "differs from the models" in process.stderr and "locale" in process.stderr
    assert await on_database(url, current_revision) is None


async def test_adoption_refuses_empty_and_already_migrated_databases(postgres_url):
    empty, migrated = await postgres_url(), await postgres_url()
    alembic(migrated, "upgrade", "head")
    assert await adopt(empty) == (False, "Database has no application tables; create them with "
                                         "`alembic -c web/alembic.ini upgrade head`.")
    assert await on_database(empty, lambda connection: inspect(connection).get_table_names()) == []
    adopted, message = await adopt(migrated)
    assert not adopted and f"already managed by migrations (revision {head_revision()})" in message
