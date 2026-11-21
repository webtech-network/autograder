"""Tracing setup for the API and the sandbox manager images (#489); the ``sandbox`` extra.

Tracing is off unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set: nothing is
instrumented and no span is exported. When it is set, ``setup_tracing`` builds
one tracer provider for the process (OTLP over HTTP/protobuf, batched in a
background thread, so a slow or absent collector never delays a request) and
the standard ``OTEL_*`` variables apply: ``OTEL_SERVICE_NAME`` (default: the
service's ``SERVICE_NAME``), ``OTEL_RESOURCE_ATTRIBUTES``, ``OTEL_TRACES_SAMPLER``
(default ``parentbased_always_on``) and the exporter's own settings.

What never reaches an exported span, whatever an instrumentation records: the
raw request path or query string and the full URL (sandbox handle IDs are
bearer-like capabilities, user IDs identify students), the client address and
exception messages and stack traces (the logs keep those, with the same
``trace_id``). Server spans keep the matched route template.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
from opentelemetry.sdk.trace.sampling import _get_from_env_or_default as configured_sampler
from opentelemetry.trace import SpanKind

from sandbox_manager.tracing import UNMATCHED_ROUTE, tracer_provider, use_tracer_provider

#: Probes and scrapes are never traced (``re.search`` on the request URL).
NOT_TRACED_URLS = r"/health$,/ready$,/metrics$"

#: Raw-path attributes, replaced by the route template.
_PATH_ATTRIBUTES = ("url.path", "http.target")
#: Full URLs, query strings and the peer's address: dropped from every span.
_DROPPED_ATTRIBUTES = frozenset((
    "http.url", "url.full", "url.query", "http.client_ip", "client.address", "client.port",
    "net.peer.ip", "net.peer.port", "net.sock.peer.addr", "net.sock.peer.port",
    "network.peer.address", "network.peer.port",
))
#: Exception event attributes kept (message and stack trace may hold handles or student data).
_KEPT_EXCEPTION_ATTRIBUTES = frozenset(("exception.type", "exception.escaped"))

logger = logging.getLogger(__name__)


def tracing_requested() -> bool:
    """Whether this process should export traces (``OTEL_EXPORTER_OTLP_ENDPOINT`` is set)."""
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())


def setup_tracing(service_name: str, *, exporter=None):
    """Build this process's tracer provider once; ``None`` when tracing is off.

    ``exporter`` replaces the OTLP exporter (tests pass an in-memory one, which
    also turns tracing on). Every exporter receives redacted spans.
    """
    if tracer_provider() is not None:
        return tracer_provider()
    if exporter is None and not tracing_requested():
        return None
    if exporter is None:
        exporter = OTLPSpanExporter()
    # OTEL_SERVICE_NAME, when set, wins over the service's SERVICE_NAME.
    attributes = {} if os.getenv("OTEL_SERVICE_NAME", "").strip() else {SERVICE_NAME: service_name}
    provider = TracerProvider(resource=Resource.create(attributes), sampler=_sampler())
    provider.add_span_processor(BatchSpanProcessor(_redacting(exporter)))
    use_tracer_provider(provider)
    logger.info("Tracing enabled: spans are exported over OTLP")
    return provider


def shutdown_tracing() -> None:
    """Flush and stop the provider (idempotent); tracing is off afterwards."""
    provider = tracer_provider()
    use_tracer_provider(None)
    if provider is not None:
        provider.shutdown()


def _sampler():
    """The configured sampler (``OTEL_TRACES_SAMPLER``), except that a client span never starts a trace.

    Database queries and outgoing HTTP calls are traced inside a request or a
    grading attempt only: the idle worker's queue polls produce no traces.
    """
    configured = configured_sampler()

    class NoRootClientSpans(Sampler):
        """Drops a client span that would start a trace; defers everything else."""

        def should_sample(self, parent_context, trace_id, name, kind=None, attributes=None,  # pylint: disable=too-many-arguments
                          links=None, trace_state=None):
            parent = trace.get_current_span(parent_context).get_span_context()
            if kind == SpanKind.CLIENT and not parent.is_valid:
                return SamplingResult(Decision.DROP)
            return configured.should_sample(parent_context, trace_id, name, kind, attributes, links, trace_state)

        def get_description(self):
            return f"NoRootClientSpans{{{configured.get_description()}}}"

    return NoRootClientSpans()


def _redacting(exporter):
    def redacted(span):
        attributes = {key: value for key, value in (span.attributes or {}).items()
                      if key not in _DROPPED_ATTRIBUTES}
        for key in _PATH_ATTRIBUTES:
            if key in attributes:
                attributes[key] = attributes.get("http.route") or UNMATCHED_ROUTE
        events = [Event(event.name, {key: value for key, value in (event.attributes or {}).items()
                                     if key in _KEPT_EXCEPTION_ATTRIBUTES}, event.timestamp)
                  if event.name == "exception" else event for event in span.events]
        return ReadableSpan(name=span.name, context=span.context, parent=span.parent, resource=span.resource,
                            attributes=attributes, events=events, links=span.links, kind=span.kind,
                            status=span.status, start_time=span.start_time, end_time=span.end_time,
                            instrumentation_scope=span.instrumentation_scope)

    class RedactingExporter(SpanExporter):
        """Exports redacted copies of the spans through ``exporter``."""

        def export(self, spans):
            return exporter.export([redacted(span) for span in spans])

        def shutdown(self):
            exporter.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return exporter.force_flush(timeout_millis)

    return RedactingExporter()


def instrument_fastapi(application) -> None:
    """Trace every request of ``application`` except probes, once tracing is set up."""
    if tracer_provider() is None or getattr(application, "_is_instrumented_by_opentelemetry", False):
        return
    # The ASGI receive/send sub-spans double the span count and say nothing here.
    FastAPIInstrumentor.instrument_app(application, tracer_provider=tracer_provider(), excluded_urls=NOT_TRACED_URLS,
                                       exclude_spans=["receive", "send"])
