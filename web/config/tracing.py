"""API tracing: requests, database statements and AI provider calls (``sandbox_manager.tracing``)."""
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from sandbox_manager.tracing_setup import instrument_fastapi, setup_tracing


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
