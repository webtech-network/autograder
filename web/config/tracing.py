"""API tracing: requests, database statements and AI provider calls (``sandbox_manager.tracing``)."""
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from opentelemetry.trace import Status, StatusCode

from sandbox_manager.tracing_setup import instrument_fastapi, setup_tracing, shutdown_tracing


def setup_api_tracing(application, *, service_name: str, engine=None) -> None:
    """Instrument the API when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set; otherwise do nothing.

    Database spans carry the statement with its placeholders, never the bound
    parameters (submissions, tokens and user IDs). The AI provider's ``httpx``
    calls are traced without bodies. Both are client spans, traced only inside a
    request or a grading attempt.
    """
    provider = setup_tracing(service_name)
    if provider is None:
        return
    instrument_fastapi(application)
    # Both instrumentors patch process-wide: the first application of the process owns them.
    httpx_instrumentor = HTTPXClientInstrumentor()
    if not httpx_instrumentor.is_instrumented_by_opentelemetry:
        httpx_instrumentor.instrument(tracer_provider=provider)
    sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
    if engine is not None and not sqlalchemy_instrumentor.is_instrumented_by_opentelemetry:
        sqlalchemy_instrumentor.instrument(engine=engine.sync_engine, tracer_provider=provider,
                                           enable_commenter=False)


def shutdown_api_tracing() -> None:
    """Export the batched spans, then undo what ``setup_api_tracing`` installed process-wide."""
    for instrumentor in (HTTPXClientInstrumentor(), SQLAlchemyInstrumentor()):
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.uninstrument()
    shutdown_tracing()


def record_attempt_outcome(outcome: dict) -> None:
    """Name the active grading attempt span's result: its status and published error code, never the message."""
    span = trace.get_current_span()
    if not span.is_recording():
        return
    span.set_attribute("autograder.outcome.status", str(outcome.get("status")))
    error = outcome.get("error") or {}
    if error.get("code"):
        span.set_attribute("error.type", str(error["code"]))
        span.set_status(Status(StatusCode.ERROR))
