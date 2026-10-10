"""Real PostgreSQL claims, restart recovery and publication races.

Set TEST_POSTGRES_URL to a disposable PostgreSQL deployment. Every test creates
and drops its own schema; SQLite cannot prove SKIP LOCKED or publication fencing.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
import platform
from threading import Event
from time import monotonic
from uuid import uuid4

from httpx import AsyncClient, ASGITransport
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from autograder.models.capabilities import HostCapabilities
from web.core.config import Settings
from web.database.base import Base
from web.database.models.submission import Submission, SubmissionStatus
from web.database.models.grading_attempt import GradingAttempt
from web.database.models.submission_result import SubmissionResult
from web.main import create_app
from web.repositories import SubmissionRepository
from web.service.grading_service import failed_outcome
from web.service.outcome_delivery import StaleAttemptError, publish_finalized, write_receipt
from web.service.worker import DurableWorker
from tests.web.test_contracts_v1 import definition


@pytest.fixture
async def postgres_sessions():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required for PostgreSQL worker guarantees")
    schema = "test_workers_" + uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}}, pool_size=10, max_overflow=20)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
async def pg_app(postgres_sessions, tmp_path):
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), WORKER_COUNT=2,
                              LEASE_SECONDS=0.6, POLL_SECONDS=0.01, MAX_ATTEMPTS=2),
                     session_factory=postgres_sessions, capabilities=HostCapabilities(), start_workers=False)
    app.state.host.ready = True
    yield app
    await app.state.host.close()


@pytest.fixture
async def pg_client(pg_app):
    async with AsyncClient(transport=ASGITransport(app=pg_app), base_url="http://test") as client:
        yield client


async def accept(client, **overrides):
    config = await client.post("/api/v1/configs", json={"external_assignment_id": "assignment", "definition": definition()})
    assert config.status_code == 200
    payload = {"external_assignment_id": "assignment", "external_user_id": "student", "username": "Student",
               "files": [{"filename": "main.py", "content": "print('ok')\r\n", "changed_lines": [], "file_metadata": {"change": "added"}}],
               "locale": "pt-br", "evaluation_scope": {"scoped_files": ["main.py"]}}
    payload.update(overrides)
    response = await client.post("/api/v1/submissions", json=payload)
    assert response.status_code == 202
    assert response.headers["Location"] == f'/api/v1/submissions/{response.json()["id"]}'
    return config.json(), response.json()["id"], payload


async def expire(sessions, submission_id):
    async with sessions() as session:
        row = await session.get(Submission, submission_id)
        row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)
        await session.commit()


@pytest.mark.asyncio
async def test_competing_workers_claim_one_attempt(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    hosts = [DurableWorker(postgres_sessions, pg_app.state.host.settings) for _ in range(8)]
    claims = await asyncio.gather(*(worker.claim() for worker in hosts))
    assert len([claim for claim in claims if claim is not None]) == 1
    async with postgres_sessions() as session:
        row = await session.get(Submission, submission_id)
        assert row.status == SubmissionStatus.PROCESSING and row.attempt_count == 1
        assert await session.scalar(select(func.count()).select_from(GradingAttempt)) == 1


@pytest.mark.asyncio
async def test_restart_uses_exact_saved_input_after_definition_deactivation(pg_app, pg_client, postgres_sessions):
    config, submission_id, payload = await accept(pg_client)
    update = await pg_client.patch(f'/api/v1/configs/{config["id"]}',
                                   headers={"If-Match": f'"{config["version"]}"'}, json={"is_active": False})
    assert update.status_code == 200
    seen = []

    async def evaluate_saved(request, capabilities):
        seen.append(request)
        return failed_outcome(request)

    restarted = create_app(pg_app.state.host.settings, session_factory=postgres_sessions,
                           capabilities=HostCapabilities(), evaluator=evaluate_saved, start_workers=False)
    await restarted.state.host.worker.run_once()
    saved = seen[0]
    assert saved.submission_id == submission_id
    assert saved.locale == payload["locale"]
    assert saved.evaluation_scope == payload["evaluation_scope"]
    assert saved.submission_files["main.py"] == payload["files"][0]
    assert saved.definition_hash == config["definition_hash"] and saved.configuration_version == 1
    assert (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()["status"] == "failed"
    await restarted.state.host.close()


@pytest.mark.asyncio
async def test_stale_worker_cannot_publish_after_lease_reclaim(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    first = await pg_app.state.host.worker.claim()
    await expire(postgres_sessions, submission_id)
    second = await pg_app.state.host.worker.claim()
    assert first[1] != second[1]
    with pytest.raises(StaleAttemptError):
        await publish_finalized(postgres_sessions, submission_id, failed_outcome(first[0]),
                                directory=pg_app.state.host.settings.RECEIPT_DIR, attempt_id=first[1])
    final = failed_outcome(second[0])
    await publish_finalized(postgres_sessions, submission_id, final,
                            directory=pg_app.state.host.settings.RECEIPT_DIR, attempt_id=second[1])
    with pytest.raises(StaleAttemptError):
        await publish_finalized(postgres_sessions, submission_id, failed_outcome(first[0]),
                                directory=pg_app.state.host.settings.RECEIPT_DIR, attempt_id=first[1])
    async with postgres_sessions() as session:
        result = await session.scalar(select(SubmissionResult).where(SubmissionResult.submission_id == submission_id))
        assert result.outcome["execution_id"] == final["execution_id"]


@pytest.mark.asyncio
async def test_expired_attempt_budget_reaches_safe_terminal_recovery_failure(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    for _ in range(pg_app.state.host.settings.MAX_ATTEMPTS):
        assert await pg_app.state.host.worker.claim() is not None
        await expire(postgres_sessions, submission_id)
    assert await pg_app.state.host.worker.claim() is None
    poll = (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()
    assert poll["status"] == "failed" and poll["final_score"] is None
    assert poll["error"]["code"] == "RECOVERY_EXHAUSTED"
    async with postgres_sessions() as session:
        statuses = list((await session.scalars(select(GradingAttempt.status))).all())
        assert statuses == ["expired", "expired"]


@pytest.mark.asyncio
async def test_restart_replays_retained_outcome_before_new_attempt(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    request, attempt_id = await pg_app.state.host.worker.claim()
    final = failed_outcome(request)
    path = write_receipt(submission_id, final, directory=pg_app.state.host.settings.RECEIPT_DIR, attempt_id=attempt_id)
    await expire(postgres_sessions, submission_id)
    assert await pg_app.state.host.worker.claim() is None
    assert not path.exists()
    async with postgres_sessions() as session:
        row = await session.get(Submission, submission_id)
        assert row.status == SubmissionStatus.FAILED and row.attempt_count == 1
        result = await session.scalar(select(SubmissionResult).where(SubmissionResult.submission_id == submission_id))
        assert result.outcome["execution_id"] == final["execution_id"]


@pytest.mark.asyncio
async def test_failed_acceptance_rolls_back_flushed_job(pg_app, pg_client, postgres_sessions, monkeypatch):
    await pg_client.post("/api/v1/configs", json={"external_assignment_id": "assignment", "definition": definition()})
    original = SubmissionRepository.create

    async def fail_after_flush(self, **kwargs):
        await original(self, **kwargs)
        raise RuntimeError("database write interrupted")

    monkeypatch.setattr(SubmissionRepository, "create", fail_after_flush)
    with pytest.raises(RuntimeError):
        await pg_client.post("/api/v1/submissions", json={"external_assignment_id": "assignment",
            "external_user_id": "student", "username": "Student", "files": [{"filename": "main.py", "content": "ok"}]})
    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Submission)) == 0


@pytest.mark.asyncio
async def test_cancelled_wrapper_drains_thread_renews_lease_and_publishes(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    started, release, exited = Event(), Event(), Event()

    def run_thread(request):
        started.set()
        assert release.wait(timeout=10)
        exited.set()
        return failed_outcome(request)

    async def evaluate_thread(request, capabilities):
        return await asyncio.to_thread(run_thread, request)

    worker = DurableWorker(postgres_sessions, pg_app.state.host.settings, evaluator=evaluate_thread)
    task = asyncio.create_task(worker.run_once())
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    try:
        await asyncio.sleep(pg_app.state.host.settings.LEASE_SECONDS * 1.5)
        assert not task.done() and not exited.is_set()
        assert await pg_app.state.host.worker.claim() is None
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert exited.is_set()
    assert (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()["status"] == "failed"


@pytest.mark.asyncio
async def test_burst_acceptance_is_separate_from_active_execution(pg_app, pg_client, postgres_sessions):
    await pg_client.post("/api/v1/configs", json={"external_assignment_id": "assignment", "definition": definition()})
    payload = {"external_assignment_id": "assignment", "external_user_id": "student", "username": "Student",
               "files": [{"filename": "main.py", "content": "print('ok')"}]}
    started = monotonic()
    responses = await asyncio.gather(*(pg_client.post("/api/v1/submissions", json=payload) for _ in range(200)))
    elapsed = monotonic() - started
    assert all(response.status_code == 202 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 200
    assert len(pg_app.state.host.worker.tasks) == 0
    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Submission)
                                    .where(Submission.status == SubmissionStatus.PENDING, Submission.attempt_count == 0)) == 200
    print(f"200 durable acknowledgments in {elapsed:.3f}s; platform={platform.machine()}; logical_cpus={os.cpu_count()}; "
          "workload=1 tiny Python source/config per request; workers=disabled; no sandbox throughput claim")
