"""Real PostgreSQL claims, restart recovery and publication races.

Set TEST_POSTGRES_URL to a disposable PostgreSQL deployment and run
`make test-postgres`. Every test creates and drops its own schema; SQLite cannot
prove SKIP LOCKED or publication fencing. Without the URL these tests error
instead of skipping, so a missing database never passes as green.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
import platform
from threading import Event
from types import SimpleNamespace
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
from tests.process_results import exited
from tests.web.test_contracts_v1 import definition


PG_TOKEN = "postgres-worker-test-token"


@pytest.fixture
async def postgres_sessions():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.fail("TEST_POSTGRES_URL is required for the PostgreSQL tier (make test-postgres)", pytrace=False)
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
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), WORKER_COUNT=2, INTEGRATION_TOKEN=PG_TOKEN,
                              LEASE_SECONDS=0.6, POLL_SECONDS=0.01, MAX_ATTEMPTS=2),
                     session_factory=postgres_sessions, capabilities=HostCapabilities(), start_workers=False)
    app.state.host.ready = True
    yield app
    await app.state.host.close()


@pytest.fixture
async def pg_client(pg_app):
    async with AsyncClient(transport=ASGITransport(app=pg_app), base_url="http://test",
                           headers={"Authorization": f"Bearer {PG_TOKEN}"}) as client:
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
    """200 concurrent acceptances commit durably while no worker runs.

    In-process (ASGI transport, workers disabled): this does not measure HTTP
    serving, worker throughput, sandbox capacity or acceptance under grading load.
    scripts/capacity_benchmark.py measures those against a running stack.
    """
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


STATIC_DEFINITION = {"schema_version": "2.0", "languages": ["python"],
                     "criteria": {"base": {"tests": [
                         {"id": "tag", "type": "has_tag", "name": "Tag", "file": "index.html",
                          "parameters": {"tag": "main"}}]}}}


@pytest.mark.asyncio
async def test_an_attempt_past_its_deadline_is_a_retryable_failure_without_lease_renewal(
        pg_app, pg_client, postgres_sessions):
    """A grading thread that never returns cannot hold its submission: at the attempt's
    deadline (a static definition: the margin alone) the worker publishes a retryable
    infrastructure failure, stops renewing the lease and never publishes the late result."""
    await pg_client.post("/api/v1/configs", json={"external_assignment_id": "static", "definition": STATIC_DEFINITION})
    response = await pg_client.post("/api/v1/submissions", json={
        "external_assignment_id": "static", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "index.html", "content": "<main></main>"}]})
    submission_id = response.json()["id"]
    started, release, exited = Event(), Event(), Event()

    def blocked(request):
        started.set()
        assert release.wait(timeout=30)
        exited.set()
        return failed_outcome(request, "EXECUTION_ERROR")  # never published: the attempt already ended

    async def evaluate_blocked(request, capabilities):
        return await asyncio.to_thread(blocked, request)

    # One attempt: on the last attempt of the budget the retryable failure is published.
    settings = replace(pg_app.state.host.settings, MAX_ATTEMPTS=1)
    worker = DurableWorker(postgres_sessions, settings, HostCapabilities(), evaluator=evaluate_blocked,
                           attempt_margin=1.0)
    claimed_at = monotonic()
    try:
        assert await asyncio.wait_for(worker.run_once(), timeout=15) is True
        elapsed = monotonic() - claimed_at
        assert started.is_set() and not exited.is_set()  # the thread is still blocked
        [abandoned] = worker.abandoned  # counted while its thread still runs
        assert 1.0 <= elapsed < 1.0 + settings.LEASE_SECONDS  # its deadline, not the thread, ended it
        poll = (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()
        assert poll["status"] == "failed" and poll["final_score"] is None
        assert (poll["error"]["code"], poll["error"]["retryable"], poll["error"]["category"]) == (
            "ATTEMPT_DEADLINE_EXCEEDED", True, "capability")
        async with postgres_sessions() as session:
            renewed_until = (await session.get(Submission, submission_id)).lease_until
    finally:
        release.set()
    assert await asyncio.to_thread(exited.wait, 10)
    await asyncio.wait({abandoned}, timeout=10)
    assert worker.abandoned == set()  # no longer counted once its thread finished
    async with postgres_sessions() as session:
        row = await session.get(Submission, submission_id)
        assert row.lease_until == renewed_until  # never renewed after the deadline
        result = await session.scalar(select(SubmissionResult).where(SubmissionResult.submission_id == submission_id))
        assert result.outcome["error"]["code"] == "ATTEMPT_DEADLINE_EXCEEDED"


@pytest.mark.asyncio
async def test_an_expired_attempt_stops_renewing_even_while_its_thread_runs(pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    request, attempt_id = await pg_app.state.host.worker.claim()
    async with postgres_sessions() as session:
        claimed = (await session.get(Submission, submission_id)).lease_until
    expired = SimpleNamespace(remaining=lambda: 0.0)
    renewer = asyncio.create_task(pg_app.state.host.worker.heartbeat(request.submission_id, attempt_id,
                                                                     asyncio.Event(), expired))
    await asyncio.wait_for(renewer, timeout=pg_app.state.host.settings.LEASE_SECONDS * 3)
    async with postgres_sessions() as session:
        assert (await session.get(Submission, submission_id)).lease_until == claimed


# ----- execution retry (COR-03): retryable failures are retried within the attempt budget -----

class FakeSession:
    """An execution session whose program prints ``output``."""
    def __init__(self, output):
        self.output = output

    def prepare_workdir(self, files):
        pass

    def run_process(self, request):
        return exited(self.output)

    def close(self):
        pass


class FlakyExecution:
    """An execution capability unavailable for its first ``failures`` acquisitions (``None``: always)."""
    def __init__(self, failures=None, output="Hello"):
        self.failures, self.output, self.acquisitions = failures, output, 0

    def __call__(self, language, budget):
        self.acquisitions += 1
        if self.failures is None or self.acquisitions <= self.failures:
            raise ConnectionError("the sandbox service is restarting")
        return FakeSession(self.output)


def retrying_worker(sessions, settings, execution, **overrides):
    return DurableWorker(sessions, replace(settings, **{"MAX_ATTEMPTS": 3, "RETRY_SECONDS": 7.0, **overrides}),
                         HostCapabilities(execution=execution))


async def attempt_history(sessions, submission_id):
    async with sessions() as session:
        return [(attempt.number, attempt.status) for attempt in (await session.scalars(
            select(GradingAttempt).where(GradingAttempt.submission_id == submission_id)
            .order_by(GradingAttempt.number))).all()]


async def released_state(sessions, submission_id):
    """The row and its last attempt after a release: (status, owner, backoff seconds, stored results)."""
    async with sessions() as session:
        row = await session.get(Submission, submission_id)
        last = await session.scalar(select(GradingAttempt).where(GradingAttempt.submission_id == submission_id)
                                    .order_by(GradingAttempt.number.desc()).limit(1))
        results = await session.scalar(select(func.count()).select_from(SubmissionResult)
                                       .where(SubmissionResult.submission_id == submission_id))
        return row.status, row.attempt_id, (row.lease_until - last.finished_at).total_seconds(), results


@pytest.mark.asyncio
async def test_retryable_failures_then_success_publish_one_completed_grade_with_attempt_history(
        pg_app, pg_client, postgres_sessions):
    """Before COR-03 the first CAPABILITY_UNAVAILABLE was published as the terminal outcome."""
    _, submission_id, _ = await accept(pg_client)
    execution = FlakyExecution(failures=2)
    worker = retrying_worker(postgres_sessions, pg_app.state.host.settings, execution)
    for attempt, backoff in ((1, 7.0), (2, 14.0)):
        assert await worker.run_once() is True
        # Not yet graded: no terminal row, polling unchanged, nobody owns the row during the backoff.
        assert await released_state(postgres_sessions, submission_id) == (
            SubmissionStatus.PROCESSING, None, backoff, 0)
        assert (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()["status"] == "processing"
        assert await worker.claim() is None  # the backoff holds the next attempt back
        assert execution.acquisitions == attempt
        await expire(postgres_sessions, submission_id)
    assert await worker.run_once() is True
    poll = (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()
    assert poll["status"] == "completed" and poll["final_score"] == 100
    assert await attempt_history(postgres_sessions, submission_id) == [
        (1, "released"), (2, "released"), (3, "published")]
    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SubmissionResult)) == 1
    assert await worker.claim() is None and execution.acquisitions == 3


@pytest.mark.asyncio
async def test_a_permanently_retryable_failure_publishes_the_last_engine_code_at_exhaustion(
        pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    execution = FlakyExecution(failures=None)
    worker = retrying_worker(postgres_sessions, pg_app.state.host.settings, execution)
    for _ in range(2):
        assert await worker.run_once() is True
        await expire(postgres_sessions, submission_id)
    assert await worker.run_once() is True
    poll = (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()
    assert poll["status"] == "failed" and poll["final_score"] is None
    assert (poll["error"]["code"], poll["error"]["retryable"]) == ("CAPABILITY_UNAVAILABLE", True)
    assert await attempt_history(postgres_sessions, submission_id) == [
        (1, "released"), (2, "released"), (3, "published")]
    await expire(postgres_sessions, submission_id)
    assert await worker.claim() is None and execution.acquisitions == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("output, capabilities, status, code", [
    ("Goodbye", "execution", "completed", None),  # an assessed zero
    ("Hello", "none", "failed", "CAPABILITY_UNAVAILABLE"),  # the host supplies no execution: not retryable
])
async def test_assessed_zeros_and_non_retryable_failures_publish_on_the_first_attempt(
        pg_app, pg_client, postgres_sessions, output, capabilities, status, code):
    _, submission_id, _ = await accept(pg_client)
    execution = FlakyExecution(failures=0, output=output)
    worker = retrying_worker(postgres_sessions, pg_app.state.host.settings, execution)
    if capabilities == "none":
        worker.capabilities = HostCapabilities()
    assert await worker.run_once() is True
    poll = (await pg_client.get(f"/api/v1/submissions/{submission_id}")).json()
    assert poll["status"] == status and (poll["error"] or {}).get("code") == code
    if status == "completed":
        assert poll["final_score"] == 0
    else:
        assert poll["error"]["retryable"] is False
    assert await attempt_history(postgres_sessions, submission_id) == [(1, "published")]
    await expire(postgres_sessions, submission_id)
    assert await worker.claim() is None
    assert execution.acquisitions == (1 if capabilities == "execution" else 0)


@pytest.mark.asyncio
async def test_interrupted_and_retryable_attempts_share_one_budget(pg_app, pg_client, postgres_sessions):
    _, submission_id, payload = await accept(pg_client)
    execution = FlakyExecution(failures=None)
    worker = retrying_worker(postgres_sessions, pg_app.state.host.settings, execution)
    assert await worker.claim() is not None  # attempt 1 is interrupted: its process died
    await expire(postgres_sessions, submission_id)
    assert await worker.run_once() is True  # attempt 2: retryable, released
    assert await released_state(postgres_sessions, submission_id) == (SubmissionStatus.PROCESSING, None, 14.0, 0)
    await expire(postgres_sessions, submission_id)
    assert await worker.run_once() is True  # attempt 3, the last: published
    assert await attempt_history(postgres_sessions, submission_id) == [
        (1, "expired"), (2, "released"), (3, "published")]
    # A released attempt then interrupted on the last attempt ends in RECOVERY_EXHAUSTED.
    other = (await pg_client.post("/api/v1/submissions", json=payload)).json()["id"]
    worker.settings = replace(worker.settings, MAX_ATTEMPTS=2)
    assert await worker.run_once() is True
    await expire(postgres_sessions, other)
    assert await worker.claim() is not None
    await expire(postgres_sessions, other)
    assert await worker.claim() is None
    poll = (await pg_client.get(f"/api/v1/submissions/{other}")).json()
    assert poll["error"]["code"] == "RECOVERY_EXHAUSTED"
    assert await attempt_history(postgres_sessions, other) == [(1, "released"), (2, "expired")]


@pytest.mark.asyncio
async def test_only_the_owning_attempt_can_release_and_a_released_lease_is_never_renewed(
        pg_app, pg_client, postgres_sessions):
    _, submission_id, _ = await accept(pg_client)
    worker = retrying_worker(postgres_sessions, pg_app.state.host.settings, FlakyExecution())
    first = await worker.claim()
    await expire(postgres_sessions, submission_id)
    second = await worker.claim()
    retry = failed_outcome(first[0], "CAPABILITY_UNAVAILABLE", category="capability", retryable=True)
    with pytest.raises(StaleAttemptError):
        await worker.release(submission_id, first[1])
    assert await worker.release(submission_id, second[1]) is True
    with pytest.raises(StaleAttemptError):  # a release ends the attempt's ownership
        await worker.release(submission_id, second[1])
    with pytest.raises(StaleAttemptError):
        await publish_finalized(postgres_sessions, submission_id, retry,
                                directory=pg_app.state.host.settings.RECEIPT_DIR, attempt_id=second[1])
    async with postgres_sessions() as session:
        released_until = (await session.get(Submission, submission_id)).lease_until
    # The released attempt's renewer finds no row it owns and stops without touching the lease.
    await asyncio.wait_for(worker.heartbeat(submission_id, second[1], asyncio.Event()),
                           timeout=pg_app.state.host.settings.LEASE_SECONDS * 3)
    async with postgres_sessions() as session:
        assert (await session.get(Submission, submission_id)).lease_until == released_until
