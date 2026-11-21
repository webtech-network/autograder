"""API tracing: acceptance context on the job, linked attempt traces, DB spans without values (#489)."""
# pylint: disable=missing-function-docstring,redefined-outer-name
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from opentelemetry import trace
from httpx import ASGITransport, AsyncClient
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from sqlalchemy import update

from autograder.models.capabilities import HostCapabilities
from sandbox_manager.structured_logging import REQUEST_ID_HEADER
from sandbox_manager import tracing_setup
from sandbox_manager.tracing import linked_root_span, tracer_provider
from sandbox_manager.tracing_setup import setup_tracing, shutdown_tracing
from tests.web.test_contracts_v1 import definition
from web.config.tracing import setup_api_tracing
from web.core.config import Settings
from web.database.models.submission import Submission
from web.service.grading_service import evaluate, failed_outcome

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
    return " ".join([span.name, span.status.description or "", *(str(value) for value in span.attributes.values())])


def test_create_app_instruments_the_api_when_an_endpoint_is_set(monkeypatch, session_factory, tmp_path):
    from web.main import create_app
    monkeypatch.setattr(tracing_setup, "OTLPSpanExporter", InMemorySpanExporter)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4318")
    try:
        app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), INTEGRATION_TOKEN=TOKEN),
                         session_factory=session_factory, capabilities=HostCapabilities(), start_workers=False)
        assert tracer_provider() is not None and app._is_instrumented_by_opentelemetry  # pylint: disable=protected-access
        assert HTTPXClientInstrumentor().is_instrumented_by_opentelemetry
        assert tracer_provider().resource.attributes["service.name"] == "autograder-api"
    finally:
        HTTPXClientInstrumentor().uninstrument()
        shutdown_tracing()


@pytest.mark.asyncio
async def test_probes_are_not_traced(traced):
    _, client, spans, _ = traced
    assert (await client.get("/api/v1/health")).status_code == 200
    assert (await client.get("/api/v1/ready")).status_code == 200
    assert not [span for span in spans() if span.kind == SpanKind.SERVER]


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming", [f"00-{PRISMA_TRACE}-00f067aa0ba902b7-00", "00-bad-01"])
async def test_an_unsampled_or_invalid_caller_context_stores_no_traceparent(traced, session_factory, incoming):
    app, client, spans, _ = traced
    submission_id = await accept(client, traceparent=incoming)
    async with session_factory() as session:
        row = await session.get(Submission, submission_id)
    sampled = [span for span in spans() if span.attributes.get("http.route") == "/api/v1/submissions"]
    if incoming.endswith("-00"):
        assert row.traceparent is None and not sampled  # the caller chose not to sample
    else:  # an invalid context is replaced by a new trace of the API's own
        assert row.traceparent.split("-")[2] == f"{sampled[0].context.span_id:016x}"
    assert await asyncio.create_task(app.state.host.worker.run_once()) is True
    [attempt] = [span for span in spans() if span.name == "grading.attempt"]
    assert len(attempt.links) == (0 if row.traceparent is None else 1)


@pytest.mark.asyncio
async def test_each_retry_is_its_own_trace_linked_to_the_same_acceptance(traced, session_factory):
    app, client, spans, _ = traced
    submission_id = await accept(client)
    worker = app.state.host.worker
    calls = []

    async def retryable_once(request, capabilities=None):
        calls.append(request)
        if len(calls) == 1:
            return failed_outcome(request, "SANDBOX_ERROR", "x", category="capability", retryable=True)
        return await evaluate(request, capabilities)
    worker.evaluator = retryable_once
    assert await asyncio.create_task(worker.run_once()) is True
    async with session_factory() as session:  # the backoff has passed
        await session.execute(update(Submission).where(Submission.id == submission_id)
                              .values(lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await session.commit()
    assert await asyncio.create_task(worker.run_once()) is True
    attempts = [span for span in spans() if span.name == "grading.attempt"]
    assert len(attempts) == 2 and attempts[0].context.trace_id != attempts[1].context.trace_id
    assert attempts[0].links[0].context == attempts[1].links[0].context
    # Each names its result by status and published code, never by message.
    assert attempts[0].attributes["error.type"] == "SANDBOX_ERROR"
    assert attempts[0].status.status_code == StatusCode.ERROR and attempts[0].status.description is None
    assert attempts[1].attributes["autograder.outcome.status"] in ("completed", "failed")


class _Answer(BaseHTTPRequestHandler):
    def do_POST(self):  # pylint: disable=invalid-name
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


def test_ai_provider_calls_are_client_spans_inside_a_trace_only(traced):
    _, _, spans, exporter = traced
    server = HTTPServer(("127.0.0.1", 0), _Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions?key=secret-query"
    try:
        exporter.clear()
        with httpx.Client() as http:
            http.post(url, json={"prompt": "tracing-secret-source"})  # outside any trace
            assert not spans()
            with linked_root_span("grading.attempt", None, {}):
                http.post(url, json={"prompt": "tracing-secret-source"})
    finally:
        server.shutdown()
    [call] = [span for span in spans() if span.kind == SpanKind.CLIENT]
    attempt = [span for span in spans() if span.name == "grading.attempt"][0]
    assert call.parent.span_id == attempt.context.span_id
    assert "secret-query" not in values(call) and "tracing-secret-source" not in values(call)
    assert not {"url.full", "http.url", "url.query"} & set(call.attributes)


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


@pytest.mark.asyncio
async def test_the_idle_workers_poll_is_never_traced(traced):
    app, _, spans, _ = traced
    # Nothing to claim: the poll's statements are client spans with no trace to join.
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
