"""Tracing of the sandbox manager and its client: W3C context, redaction, no-op when off (#489)."""
# pylint: disable=missing-function-docstring,redefined-outer-name
import io
import json
import logging

import pytest
import requests
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from autograder.models.language import Language
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.remote_client import (
    RemoteSandboxContainer, RemoteSandboxError, RemoteSandboxManager, route_template,
)
from sandbox_manager.structured_logging import _ServiceHandler
from sandbox_manager.tracing import (
    UNMATCHED_ROUTE, client_span, current_trace_ids, current_traceparent, end_client_span, linked_root_span,
    tracer_provider,
)
from sandbox_manager.tracing_setup import setup_tracing, shutdown_tracing, tracing_requested
from tests.unit.sandbox.test_control_api import AUTH, TOKEN, FakeManager, acquire

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT = f"00-{TRACE_ID}-00f067aa0ba902b7-01"


@pytest.fixture
def spans():
    """Tracing on, exporting to memory; ``spans()`` flushes and returns the finished spans."""
    exporter = InMemorySpanExporter()
    provider = setup_tracing("autograder-sandbox-manager", exporter=exporter)

    def finished():
        provider.force_flush()
        return list(exporter.get_finished_spans())
    yield finished
    shutdown_tracing()


@pytest.fixture(autouse=True)
def restore_logging():
    yield
    root = logging.getLogger()
    for handler in [h for h in root.handlers if isinstance(h, _ServiceHandler)]:
        root.removeHandler(handler)


def control_api(**settings):
    manager = FakeManager()
    return TestClient(create_app(ControlSettings(token=TOKEN, reaper_interval_seconds=3600, **settings),
                                 lambda: manager)), manager


def every_value(span):
    values = [str(value) for value in span.attributes.values()]
    for event in span.events:
        values += [str(value) for value in event.attributes.values()]
    return " ".join(values + [span.name])


def test_without_an_endpoint_nothing_is_traced_and_no_id_is_logged(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert not tracing_requested() and setup_tracing("autograder-sandbox-manager") is None
    client, _ = control_api(json_logs=True)
    with client:
        stream = io.StringIO()
        for handler in logging.getLogger().handlers:
            if isinstance(handler, _ServiceHandler):
                handler.setStream(stream)
        assert acquire(client).status_code == 200
        response = client.get("/stats", headers={**AUTH, "traceparent": PARENT})
    assert response.status_code == 200 and tracer_provider() is None
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines and not [line for line in lines if "trace_id" in line or "span_id" in line]


def test_an_endpoint_turns_tracing_on(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid:4318")
    try:
        provider = setup_tracing("autograder-sandbox-manager")
        assert provider is not None and setup_tracing("other") is provider  # once per process
        assert provider.resource.attributes["service.name"] == "autograder-sandbox-manager"
    finally:
        shutdown_tracing()
    assert tracer_provider() is None


def test_otel_service_name_wins_over_service_name(monkeypatch, spans):
    shutdown_tracing()
    monkeypatch.setenv("OTEL_SERVICE_NAME", "sandbox-staging")
    provider = setup_tracing("autograder-sandbox-manager", exporter=InMemorySpanExporter())
    assert provider.resource.attributes["service.name"] == "sandbox-staging"


def test_a_request_continues_the_callers_trace_with_its_route_template_only(spans):
    client, manager = control_api(json_logs=True)
    with client:
        stream = io.StringIO()
        for handler in logging.getLogger().handlers:
            if isinstance(handler, _ServiceHandler):
                handler.setStream(stream)
        handle = acquire(client).json()["sandbox_id"]
        response = client.post(f"/sandboxes/{handle}/process?secret=q", headers={**AUTH, "traceparent": PARENT},
                               json={"argv": ["true"], "timeout": 1})
        assert response.status_code == 200, response.text
        assert client.get("/health").status_code == 200
    assert manager.acquired
    server = [span for span in spans() if span.kind == SpanKind.SERVER]
    traced = [span for span in server if format(span.context.trace_id, "032x") == TRACE_ID]
    assert [span.name for span in traced] == ["POST /sandboxes/{sandbox_id}/process"]
    span = traced[0]
    assert span.parent.span_id == 0x00f067aa0ba902b7 and span.parent.is_remote
    assert span.attributes["http.route"] == "/sandboxes/{sandbox_id}/process"
    for leaked in (handle, "secret"):
        assert leaked not in every_value(span)
    assert not {"http.url", "url.full", "url.query", "net.peer.ip", "client.address"} & set(span.attributes)
    assert not [s for s in server if s.attributes.get("http.route") == "/health"]  # probes are not traced
    # The request's log line names the same trace and span.
    line = [json.loads(l) for l in stream.getvalue().splitlines()
            if json.loads(l).get("path") == "/sandboxes/{sandbox_id}/process"][0]
    assert line["trace_id"] == TRACE_ID and line["span_id"] == format(span.context.span_id, "016x")


class Recorder(requests.adapters.HTTPAdapter):
    """Answers every request with ``status`` (or raises ``error``) and keeps the headers sent."""

    def __init__(self, status=200, body=b"{}", error=None):
        super().__init__()
        self.status, self.body, self.error, self.sent = status, body, error, []

    def send(self, request, *args, **kwargs):  # pylint: disable=arguments-differ
        self.sent.append(request)
        if self.error is not None:
            raise self.error
        response = requests.Response()
        response.status_code, response._content, response.url = self.status, self.body, request.url  # pylint: disable=protected-access
        response.headers["Content-Type"] = "application/json"
        return response


def container(adapter):
    sandbox = RemoteSandboxContainer("handle-secret", Language.PYTHON, "http://sandbox:8001", token="tok")
    sandbox._session.mount("http://", adapter)  # pylint: disable=protected-access
    return sandbox


def test_sandbox_calls_send_traceparent_and_record_the_route_never_the_handle(spans):
    adapter = Recorder(body=b'{"path": "out.txt", "content_bytes": "", "size": 0, '
                            b'"content_text": "", "encoding": "utf-8"}')
    with trace.get_tracer("t", tracer_provider=tracer_provider()).start_as_current_span("grading.attempt") as parent:
        container(adapter).extract_file("out.txt")
    client = [span for span in spans() if span.kind == SpanKind.CLIENT]
    assert [span.name for span in client] == ["GET /sandboxes/{sandbox_id}/files"]
    span = client[0]
    assert span.parent.span_id == parent.get_span_context().span_id
    header = adapter.sent[0].headers["traceparent"]
    assert header.split("-")[1:3] == [f"{span.context.trace_id:032x}", f"{span.context.span_id:016x}"]
    assert int(header.split("-")[3], 16) & 1  # sampled
    assert span.attributes["http.response.status_code"] == 200
    assert "handle-secret" not in every_value(span) and "out.txt" not in every_value(span)


def test_failed_sandbox_calls_record_only_the_status_or_error_type(spans):
    tracer = trace.get_tracer("t", tracer_provider=tracer_provider())
    with tracer.start_as_current_span("grading.attempt"):
        with pytest.raises(RemoteSandboxError):
            container(Recorder(status=500, body=b'{"detail": "boom"}')).extract_file("x")
        with pytest.raises(RemoteSandboxError):
            container(Recorder(error=requests.ConnectionError("http://sandbox:8001/sandboxes/handle-secret"))) \
                .extract_file("x")
    errors = {span.attributes.get("error.type"): span for span in spans() if span.kind == SpanKind.CLIENT}
    assert set(errors) == {"500", "ConnectionError"}
    assert all(span.status.status_code == StatusCode.ERROR for span in errors.values())
    assert all("handle-secret" not in every_value(span) for span in errors.values())


def test_client_calls_outside_any_trace_start_none(spans):
    adapter = Recorder(body=b'{"status": "removed"}')
    manager = RemoteSandboxManager("http://sandbox:8001", token="tok")
    manager._session.mount("http://", adapter)  # pylint: disable=protected-access
    manager.get_pool_stats()
    assert not spans()
    # The sandbox manager is told so: it does not trace the request either.
    assert not int(adapter.sent[0].headers["traceparent"].split("-")[3], 16) & 1


@pytest.mark.parametrize("method,url,route", [
    ("POST", "http://s:8001/sandboxes/python", "/sandboxes/{language}"),
    ("POST", "http://s:8001/sandboxes/h-1/prepare", "/sandboxes/{sandbox_id}/prepare"),
    ("POST", "http://s:8001/sandboxes/h-1/inject", "/sandboxes/{sandbox_id}/inject"),
    ("POST", "http://s:8001/sandboxes/h-1/process", "/sandboxes/{sandbox_id}/process"),
    ("GET", "http://s:8001/sandboxes/h-1/files?path=a", "/sandboxes/{sandbox_id}/files"),
    ("DELETE", "http://s:8001/sandboxes/h-1", "/sandboxes/{sandbox_id}"),
    ("GET", "http://s:8001/stats", "/stats"),
    ("GET", "http://s:8001/sandboxes/h-1/unknown", UNMATCHED_ROUTE),
])
def test_route_templates_are_the_control_apis_own(method, url, route):
    assert route_template(method, url) == route
    if route != UNMATCHED_ROUTE:
        app = create_app(ControlSettings(token=TOKEN), FakeManager)
        assert route in {getattr(r, "path", None) for r in app.routes}


def test_exception_events_keep_only_the_type(spans):
    tracer = trace.get_tracer("t", tracer_provider=tracer_provider())
    with pytest.raises(ValueError):
        with tracer.start_as_current_span("work"):
            raise ValueError("student secret handle-secret")
    [span] = spans()
    [event] = span.events
    assert event.name == "exception" and event.attributes["exception.type"] == "ValueError"
    assert "handle-secret" not in every_value(span)


def test_an_attempt_is_a_new_trace_linked_to_the_accepting_span(spans):
    tracer = trace.get_tracer("t", tracer_provider=tracer_provider())
    with tracer.start_as_current_span("POST /api/v1/submissions"):
        stored = current_traceparent()
        with linked_root_span("grading.attempt", stored, {"autograder.attempt.id": "a-1"}):
            assert current_trace_ids()[0] != stored.split("-")[1]
    attempt = [span for span in spans() if span.name == "grading.attempt"][0]
    assert attempt.parent is None and attempt.attributes["autograder.attempt.id"] == "a-1"
    [link] = attempt.links
    assert stored.split("-")[1:3] == [f"{link.context.trace_id:032x}", f"{link.context.span_id:016x}"]


@pytest.mark.parametrize("traceparent", [None, "", "garbage", "00-" + "0" * 32 + "-" + "0" * 16 + "-01"])
def test_an_attempt_without_a_valid_stored_context_has_no_link(spans, traceparent):
    with linked_root_span("grading.attempt", traceparent, {}):
        pass
    [attempt] = spans()
    assert not attempt.links


def test_nothing_is_stored_or_injected_for_an_unsampled_request():
    unsampled = f"00-{TRACE_ID}-00f067aa0ba902b7-00"
    from opentelemetry import propagate, context  # pylint: disable=import-outside-toplevel
    token = context.attach(propagate.extract({"traceparent": unsampled}))
    try:
        assert current_traceparent() is None
    finally:
        context.detach(token)
    assert current_traceparent() is None and current_trace_ids() == (None, None)


def test_client_span_is_inert_while_tracing_is_off():
    carrier = {}
    with client_span("GET", "/stats", carrier) as span:
        end_client_span(span, status_code=500)
    assert not carrier and not span.is_recording()
