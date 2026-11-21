"""API tracing: acceptance context on the job, linked attempt traces, DB spans without values (#489)."""
# pylint: disable=missing-function-docstring,redefined-outer-name
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from autograder.models.capabilities import HostCapabilities
from sandbox_manager.structured_logging import REQUEST_ID_HEADER
from sandbox_manager.tracing_setup import setup_tracing, shutdown_tracing
from tests.web.test_contracts_v1 import definition
from web.config.tracing import setup_api_tracing
from web.core.config import Settings
from web.database.models.submission import Submission

TOKEN = "tracing-token"
PRISMA_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
PRISMA_PARENT = f"00-{PRISMA_TRACE}-00f067aa0ba902b7-01"
STUDENT = "student-7d1e"
SOURCE = "print('tracing-secret-source')\n"


@pytest.fixture
async def traced(session_factory, db_engine, tmp_path):
    """A traced API on the test database; yields the app, a client and a reader of finished spans."""
    from web.main import create_app
    exporter = InMemorySpanExporter()
    provider = setup_tracing("autograder-api", exporter=exporter)
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), INTEGRATION_TOKEN=TOKEN),
                     session_factory=session_factory, capabilities=HostCapabilities(), start_workers=False)
    # The fixture's sessions are injected, so the database is instrumented the way create_app does it.
    setup_api_tracing(app, service_name="autograder-api", engine=db_engine)
    app.state.host.ready = True

    def spans():
        provider.force_flush()
        return list(exporter.get_finished_spans())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {TOKEN}"}) as client:
            yield app, client, spans, exporter
    finally:
        await app.state.host.close()
        SQLAlchemyInstrumentor().uninstrument()
        HTTPXClientInstrumentor().uninstrument()
        shutdown_tracing()


async def accept(client, **headers):
    assert (await client.post("/api/v1/configs", json={"external_assignment_id": "traced",
                                                       "definition": definition()})).status_code == 200
    accepted = await client.post("/api/v1/submissions", headers=headers, json={
        "external_assignment_id": "traced", "external_user_id": STUDENT, "username": "Student Name",
        "files": [{"filename": "main.py", "content": SOURCE}]})
    assert accepted.status_code == 202, accepted.text
    return accepted.json()["id"]


def values(span):
    return " ".join([span.name, *(str(value) for value in span.attributes.values())])


@pytest.mark.asyncio
async def test_acceptance_stores_its_span_and_the_attempt_trace_links_back(traced, session_factory):
    app, client, spans, _ = traced
    submission_id = await accept(client, traceparent=PRISMA_PARENT, **{REQUEST_ID_HEADER: "prisma-req-9"})
    acceptance = [span for span in spans() if span.kind == SpanKind.SERVER
                  and span.attributes.get("http.route") == "/api/v1/submissions"][0]
    assert f"{acceptance.context.trace_id:032x}" == PRISMA_TRACE  # continues prisma-api's trace
    async with session_factory() as session:
        row = await session.get(Submission, submission_id)
    assert row.request_id == "prisma-req-9"
    assert row.traceparent.split("-")[1:3] == [PRISMA_TRACE, f"{acceptance.context.span_id:016x}"]

    assert await asyncio.create_task(app.state.host.worker.run_once()) is True
    [attempt] = [span for span in spans() if span.name == "grading.attempt"]
    assert attempt.parent is None and f"{attempt.context.trace_id:032x}" != PRISMA_TRACE
    assert [link.context.span_id for link in attempt.links] == [acceptance.context.span_id]
    assert attempt.attributes["autograder.submission.id"] == submission_id
    in_attempt = [span for span in spans() if span.context.trace_id == attempt.context.trace_id]
    assert [span for span in in_attempt if span.kind == SpanKind.CLIENT]  # its database statements


@pytest.mark.asyncio
async def test_database_spans_have_statements_without_values_and_never_start_a_trace(traced):
    app, client, spans, exporter = traced
    await accept(client)
    assert await asyncio.create_task(app.state.host.worker.run_once()) is True
    database = [span for span in spans() if "db.statement" in span.attributes]
    assert database and all(span.parent is not None for span in database)
    assert any("INSERT INTO submissions" in span.attributes["db.statement"] for span in database)
    for span in spans():
        for value in (STUDENT, "Student Name", "tracing-secret-source", TOKEN):
            assert value not in values(span)

    exporter.clear()
    # The idle worker's poll finds nothing: no trace at all.
    assert await asyncio.create_task(app.state.host.worker.run_once()) is False
    assert not spans()


@pytest.mark.asyncio
async def test_student_ids_in_paths_never_reach_a_span(traced):
    _, client, spans, _ = traced
    response = await client.get(f"/api/v1/submissions/user/{STUDENT}?limit=5")
    assert response.status_code == 200, response.text
    [server] = [span for span in spans() if span.kind == SpanKind.SERVER]
    assert server.attributes["http.route"] == "/api/v1/submissions/user/{external_user_id}"
    assert STUDENT not in values(server) and "limit" not in values(server)
