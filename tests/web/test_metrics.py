"""``GET /metrics`` of the HTTP service: HTTP, grading pipeline, queue and database pool (#488)."""
import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import CollectorRegistry
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from web.metrics import DatabaseMetrics
from web.service.grading_service import evaluate, failed_outcome
from tests.web.worker_support import end_retry_backoffs

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


@pytest.mark.asyncio
async def test_the_queue_reports_the_claimable_backlog(test_client, application):
    await scrape(application)
    assert value(application, "autograder_queue_submissions", state="pending") == 0
    assert value(application, "autograder_queue_oldest_age_seconds") == 0
    await submit(test_client)
    await submit(test_client, user="student-2")
    await scrape(application)
    assert value(application, "autograder_queue_up") == 1
    assert value(application, "autograder_queue_submissions", state="pending") == 2
    assert value(application, "autograder_queue_submissions", state="processing") == 0
    assert value(application, "autograder_queue_oldest_age_seconds") >= 0


@pytest.mark.asyncio
async def test_an_unreadable_queue_reports_down_and_the_scrape_still_answers(application):
    def broken_sessions():
        raise RuntimeError("database down")

    application.state.host.sessions = broken_sessions
    await scrape(application)
    assert value(application, "autograder_queue_up") == 0
    assert value(application, "autograder_queue_submissions", state="pending") is None


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
