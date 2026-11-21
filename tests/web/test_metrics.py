"""``GET /metrics`` of the HTTP service: HTTP, grading pipeline, queue and database pool (#488)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import CollectorRegistry
from sqlalchemy import null, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from web import metrics as web_metrics
from web.config.body_limit import MAX_REQUEST_BYTES
from web.database.models.submission import Submission
from web.metrics import DatabaseMetrics, GradingMetrics, QueueMetrics
from web.service import worker as worker_module
from web.service.grading_service import evaluate, failed_outcome
from web.service.outcome_delivery import OutcomeDeliveryError, StaleAttemptError
from tests.web.worker_support import end_retry_backoffs
# The PostgreSQL tier's fixtures, for the queue test that runs there (`make test-postgres`).
from tests.web.test_durable_workers import pg_app, postgres_sessions  # pylint: disable=unused-import


@pytest.fixture(autouse=True)
def fresh_queue_reads(monkeypatch):
    """Every scrape reads the queue; the reuse interval has its own test."""
    monkeypatch.setattr(web_metrics, "QUEUE_REFRESH_SECONDS", 0.0)

DEFINITION = {"schema_version": "2.0", "languages": ["python"],
              "criteria": {"base": {"tests": [
                  {"id": "imports", "type": "forbidden_import", "name": "Imports", "weight": 1,
                   "parameters": {"forbidden_imports": ["os"]}}]}}}


async def submit(client, assignment="metrics-assignment", user="student-7f3a"):
    created = await client.post("/api/v1/configs", json={"external_assignment_id": assignment,
                                                          "definition": DEFINITION})
    assert created.status_code in (200, 409), created.text  # 409: the config already exists
    submitted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": assignment, "external_user_id": user, "username": "Student Name",
        "files": [{"filename": "main.py", "content": "print(1)\n"}]})
    assert submitted.status_code == 202, submitted.text
    return submitted


async def scrape(application):
    """``/metrics`` without any credential, as Prometheus scrapes it."""
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as anonymous:
        response = await anonymous.get("/metrics")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    return response


def value(application, name, **labels):
    return application.state.host.metrics.registry.get_sample_value(name, labels)


@pytest.mark.asyncio
async def test_metrics_are_public_and_label_requests_by_route_template(test_client, application):
    submitted = await submit(test_client)
    assert (await test_client.get(submitted.headers["Location"])).status_code == 200
    response = await scrape(application)
    assert value(application, "http_server_requests_total", method="POST", route="/api/v1/submissions",
                 status="202") == 1
    assert value(application, "http_server_requests_total", method="GET",
                 route="/api/v1/submissions/{submission_id}", status="200") == 1
    # Identifiers and names never become labels or values.
    for private in ("student-7f3a", "Student Name", "metrics-assignment", submitted.headers["Location"]):
        assert private not in response.text


async def assert_queue_states(application, sessions):
    """Pending, processing and unbound rows over the real routes and claim, on ``sessions``' database."""
    host = application.state.host
    await scrape(application)
    assert value(application, "autograder_queue_up") == 1
    assert value(application, "autograder_queue_submissions", state="pending") == 0
    assert value(application, "autograder_queue_oldest_age_seconds") == 0
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test",
                           headers={"Authorization": f"Bearer {host.settings.INTEGRATION_TOKEN}"}) as client:
        for user in ("a", "b", "c"):
            await submit(client, user=user)
    async with sessions() as session:
        await session.execute(update(Submission).values(
            submitted_at=datetime.now(timezone.utc) - timedelta(seconds=120)))
        await session.commit()
    assert await host.worker.claim() is not None  # the first submission is now owned by an attempt
    async with sessions() as session:  # a row without a bound definition is never claimed work
        row = await session.scalar(select(Submission).order_by(Submission.id.desc()).limit(1))
        row.definition_snapshot = null()  # SQL NULL (None would store JSON null)
        await session.commit()
    await scrape(application)
    assert value(application, "autograder_queue_submissions", state="pending") == 1
    assert value(application, "autograder_queue_submissions", state="processing") == 1
    assert value(application, "autograder_queue_submissions", state="retry_wait") == 0
    assert 110 < value(application, "autograder_queue_oldest_age_seconds") < 600


@pytest.mark.asyncio
async def test_the_queue_reports_open_submissions_by_ownership(application, session_factory):
    await assert_queue_states(application, session_factory)


@pytest.mark.asyncio
async def test_the_queue_query_runs_on_postgresql(pg_app, postgres_sessions):  # pylint: disable=redefined-outer-name
    await assert_queue_states(pg_app, postgres_sessions)


@pytest.mark.asyncio
async def test_concurrent_scrapes_share_one_queue_read_per_interval(monkeypatch):
    monkeypatch.setattr(web_metrics, "QUEUE_REFRESH_SECONDS", 5.0)
    now = [100.0]
    queue = QueueMetrics(clock=lambda: now[0])
    reads = []

    async def read(_sessions):
        reads.append(1)
        await asyncio.sleep(0.01)
        return {"pending": len(reads)}, 0.0

    monkeypatch.setattr(QueueMetrics, "_read", staticmethod(read))
    await asyncio.gather(*(queue.refresh(None) for _ in range(20)))
    assert len(reads) == 1
    now[0] += 4.9
    await queue.refresh(None)
    assert len(reads) == 1
    now[0] += 0.2
    await queue.refresh(None)
    assert len(reads) == 2


@pytest.mark.asyncio
async def test_a_slow_queue_read_reports_down_and_logs_once(monkeypatch, caplog):
    monkeypatch.setattr(web_metrics, "QUEUE_QUERY_TIMEOUT_SECONDS", 0.01)

    async def slow(_sessions):
        await asyncio.sleep(1)

    monkeypatch.setattr(QueueMetrics, "_read", staticmethod(slow))
    registry = CollectorRegistry()
    queue = QueueMetrics()
    registry.register(queue)
    for _ in range(3):
        await queue.refresh(None)
    assert registry.get_sample_value("autograder_queue_up") == 0
    assert registry.get_sample_value("autograder_queue_oldest_age_seconds") is None
    assert [record.getMessage() for record in caplog.records].count("metrics_queue_unavailable: TimeoutError") == 1


@pytest.mark.asyncio
async def test_an_unreadable_queue_reports_down_and_the_scrape_still_answers(application):
    def broken_sessions():
        raise RuntimeError("database down")

    application.state.host.sessions = broken_sessions
    await scrape(application)
    assert value(application, "autograder_queue_up") == 0
    assert value(application, "autograder_queue_submissions", state="pending") is None
    assert value(application, "autograder_queue_oldest_age_seconds") is None


@pytest.mark.asyncio
async def test_a_completed_grading_counts_one_submission_and_one_attempt(test_client, application):
    await submit(test_client)
    worker = application.state.host.worker
    while await worker.run_once():
        pass
    await scrape(application)
    assert value(application, "autograder_submissions_total", status="completed", language="python",
                 error_category="none") == 1
    assert value(application, "autograder_grading_duration_seconds_count", language="python",
                 status="completed") == 1
    assert value(application, "autograder_grading_in_progress") == 0
    assert value(application, "autograder_queue_submissions", state="pending") == 0


@pytest.mark.asyncio
async def test_a_retried_failure_counts_per_attempt_and_the_final_outcome_once(test_client, application):
    host = application.state.host
    attempts = []

    async def flaky(request, capabilities=None):
        attempts.append(request.submission_id)
        if len(attempts) == 1:
            return failed_outcome(request, "SANDBOX_ERROR", "The sandbox failed.", category="capability",
                                  retryable=True)
        return await evaluate(request, capabilities)

    host.worker.evaluator = flaky
    await submit(test_client)
    assert await host.worker.run_once()
    await scrape(application)
    assert value(application, "autograder_queue_submissions", state="retry_wait") == 1
    assert value(application, "autograder_submissions_total", status="failed", language="python",
                 error_category="capability") is None
    assert await end_retry_backoffs(host.sessions) == 1
    assert await host.worker.run_once()
    await scrape(application)
    assert len(attempts) == 2
    assert value(application, "autograder_grading_failures_total", category="capability", code="SANDBOX_ERROR",
                 retryable="true") == 1
    assert value(application, "autograder_submissions_total", status="completed", language="python",
                 error_category="none") == 1
    assert value(application, "autograder_grading_duration_seconds_count", language="python", status="failed") == 1
    assert value(application, "autograder_queue_submissions", state="retry_wait") == 0


@pytest.mark.asyncio
async def test_pool_gauges_and_connection_timing_come_from_the_engine(tmp_path):
    registry = CollectorRegistry()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pool.sqlite'}", pool_size=3, max_overflow=4)
    DatabaseMetrics(registry).instrument(engine)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            assert registry.get_sample_value("autograder_db_pool_checked_out") == 1
        assert registry.get_sample_value("autograder_db_pool_size") == 3
        assert registry.get_sample_value("autograder_db_pool_max_overflow") == 4
        assert registry.get_sample_value("autograder_db_pool_checked_out") == 0
        assert registry.get_sample_value("autograder_db_pool_checked_in") == 1
        assert registry.get_sample_value("autograder_db_pool_overflow") == 0
        assert registry.get_sample_value("autograder_db_pool_connections_created_total") == 1
        assert registry.get_sample_value("autograder_db_pool_connect_duration_seconds_count") == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_pool_without_a_size_reports_no_gauges(tmp_path):
    registry = CollectorRegistry()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pool.sqlite'}", poolclass=NullPool)
    DatabaseMetrics(registry).instrument(engine)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        assert registry.get_sample_value("autograder_db_pool_size") is None
        assert registry.get_sample_value("autograder_db_pool_connections_created_total") == 1
    finally:
        await engine.dispose()


async def grade_with(test_client, application, evaluator):
    application.state.host.worker.evaluator = evaluator
    await submit(test_client)
    while await application.state.host.worker.run_once():
        pass
    await scrape(application)


@pytest.mark.asyncio
async def test_a_non_retryable_failure_is_final_on_its_first_attempt(test_client, application):
    async def missing_file(request, capabilities=None):  # pylint: disable=unused-argument
        return failed_outcome(request, "REQUIRED_FILE_MISSING", "A required file is missing.", category="submission")

    await grade_with(test_client, application, missing_file)
    assert value(application, "autograder_submissions_total", status="failed", language="python",
                 error_category="submission") == 1
    assert value(application, "autograder_grading_failures_total", category="submission",
                 code="REQUIRED_FILE_MISSING", retryable="false") == 1


@pytest.mark.asyncio
async def test_an_exhausted_recovery_is_counted_as_final(test_client, application):
    host = application.state.host
    await submit(test_client)
    async with host.sessions() as session:
        await session.execute(update(Submission).values(attempt_count=host.settings.MAX_ATTEMPTS))
        await session.commit()
    assert await host.worker.claim() is None
    await scrape(application)
    assert value(application, "autograder_submissions_total", status="failed", language="python",
                 error_category="internal") == 1


@pytest.mark.asyncio
async def test_a_retained_outcome_is_final_and_a_stale_attempt_is_not(test_client, application, monkeypatch):
    async def retained(*_args, **_kwargs):
        raise OutcomeDeliveryError("receipt.json")

    monkeypatch.setattr(worker_module, "publish_finalized", retained)
    await grade_with(test_client, application, evaluate)
    assert value(application, "autograder_submissions_total", status="completed", language="python",
                 error_category="none") == 1

    async def stale(*_args, **_kwargs):
        raise StaleAttemptError("A newer attempt owns this submission")

    monkeypatch.setattr(worker_module, "publish_finalized", stale)
    await grade_with(test_client, application, evaluate)
    assert value(application, "autograder_submissions_total", status="completed", language="python",
                 error_category="none") == 1
    assert value(application, "autograder_grading_duration_seconds_count", language="python",
                 status="completed") == 2
    assert value(application, "autograder_grading_in_progress") == 0


@pytest.mark.asyncio
async def test_an_attempt_that_raises_leaves_no_attempt_in_progress(test_client, application):
    async def broken(request, capabilities=None):  # pylint: disable=unused-argument
        raise RuntimeError("worker bug")

    application.state.host.worker.evaluator = broken
    await submit(test_client)
    with pytest.raises(RuntimeError):
        await application.state.host.worker.run_once()
    await scrape(application)
    assert value(application, "autograder_grading_in_progress") == 0


@pytest.mark.asyncio
async def test_requests_rejected_by_middleware_or_authentication_are_counted(application):
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as anonymous:
        oversized = await anonymous.post("/api/v1/submissions", content=b"x" * (MAX_REQUEST_BYTES + 1),
                                         headers={"Content-Type": "application/json"})
        assert oversized.status_code == 413
        assert (await anonymous.get("/api/v1/submissions/1",
                                    headers={"Authorization": "Bearer wrong"})).status_code == 401
    assert value(application, "http_server_requests_total", method="POST", route="unmatched", status="413") == 1
    assert value(application, "http_server_requests_total", method="GET",
                 route="/api/v1/submissions/{submission_id}", status="401") == 1


def test_values_outside_their_closed_set_are_reported_as_other():
    registry = CollectorRegistry()
    grading = GradingMetrics(registry)
    outcome = {"status": "weird", "error": {"category": "cosmic", "code": "NOT_A_CODE", "retryable": True}}
    grading.attempt_finished("klingon", {**outcome, "status": "failed"}, 1.0)
    grading.published("klingon", outcome)
    assert registry.get_sample_value("autograder_grading_failures_total",
                                     {"category": "other", "code": "other", "retryable": "true"}) == 1
    assert registry.get_sample_value("autograder_submissions_total",
                                     {"status": "other", "language": "other", "error_category": "other"}) == 1
