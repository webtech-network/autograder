"""Suite-wide guards."""
import pytest

#: Tracing configuration a developer's or CI shell may export (INF-5 sets them in compose).
OTEL_VARIABLES = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME", "OTEL_RESOURCE_ATTRIBUTES",
                  "OTEL_TRACES_SAMPLER", "OTEL_TRACES_SAMPLER_ARG")


@pytest.fixture(autouse=True)
def tracing_off(monkeypatch):
    """Tests never export spans unless they turn tracing on themselves, and never leave it on (#489)."""
    for name in OTEL_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    yield
    from sandbox_manager.tracing import tracer_provider  # pylint: disable=import-outside-toplevel
    left_on = tracer_provider() is not None
    if left_on:
        from sandbox_manager.tracing_setup import shutdown_tracing  # pylint: disable=import-outside-toplevel
        shutdown_tracing()
    assert not left_on, "the test left tracing on: call shutdown_tracing()"
