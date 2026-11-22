"""OpenTelemetry trace context shared by the API, the sandbox manager and the sandbox client (#489).

These helpers need only the OpenTelemetry API, a base dependency: without the
SDK, or before ``sandbox_manager.tracing_setup.setup_tracing`` installed a
provider, every span is a no-op, nothing is injected and no id is returned.
Spans never record a URL (``client_span`` takes a route template); see
``tracing_setup`` for what is removed before any span is exported.
"""
from contextlib import contextmanager
from typing import Iterator, MutableMapping, Optional, Tuple

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

TRACER_NAME = "autograder"
#: Named instead of a path no route matched (the raw path may hold a handle).
UNMATCHED_ROUTE = "<unmatched>"


def server_route(scope) -> str:
    """The template of the route that handled a request (set by FastAPI's router), else ``UNMATCHED_ROUTE``.

    The ``path`` of request log lines and the ``route`` label of HTTP metrics; server spans
    take OpenTelemetry's ``http.route`` with the same ``UNMATCHED_ROUTE`` fallback.
    """
    return getattr(scope.get("route"), "path", None) or UNMATCHED_ROUTE

_provider = None  # pylint: disable=invalid-name  # set once per process
_tracer = trace.get_tracer(TRACER_NAME)  # pylint: disable=invalid-name  # follows _provider
#: Only W3C trace context crosses a process boundary here (never ``baggage``).
_W3C = TraceContextTextMapPropagator()


def tracer_provider():
    """The provider ``tracing_setup.setup_tracing`` installed, or ``None`` when tracing is off."""
    return _provider


def use_tracer_provider(provider) -> None:
    """Install (or, with ``None``, remove) this process's provider; see ``tracing_setup``."""
    global _provider, _tracer  # pylint: disable=global-statement,invalid-name
    _provider = provider
    _tracer = trace.get_tracer(TRACER_NAME, tracer_provider=provider)


def current_trace_ids() -> Tuple[Optional[str], Optional[str]]:
    """``(trace_id, span_id)`` of the active span context in W3C hex, or ``(None, None)``.

    The context may belong to a span that was not sampled: its ids then reach
    log lines but no trace backend.
    """
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None, None
    return format(context.trace_id, "032x"), format(context.span_id, "016x")


def current_traceparent() -> Optional[str]:
    """The W3C ``traceparent`` of the active span when it is recorded (sampled), else ``None``."""
    context = trace.get_current_span().get_span_context()
    if not (context.is_valid and context.trace_flags.sampled):
        return None
    carrier: dict = {}
    _W3C.inject(carrier)
    return carrier.get("traceparent")


def _record_error(span, error: BaseException) -> None:
    """Mark ``span`` failed by ``error``'s type only (its message may hold a handle or student data)."""
    if span.is_recording():
        span.set_attribute("error.type", type(error).__name__)
        span.set_status(Status(StatusCode.ERROR))


@contextmanager
def client_span(method: str, route: str, carrier: MutableMapping[str, str]) -> Iterator[object]:
    """A client span named ``"<method> <route>"`` whose context is injected into ``carrier``.

    ``route`` is a template (``/sandboxes/{sandbox_id}/process``); the URL is never
    recorded, and an error that escapes is recorded by its type only. While
    tracing is off the span does not record and ``carrier`` is untouched.
    """
    with _tracer.start_as_current_span(
            f"{method} {route}", kind=SpanKind.CLIENT, record_exception=False, set_status_on_exception=False,
            attributes={"http.request.method": method, "url.template": route}) as span:
        _W3C.inject(carrier)
        try:
            yield span
        except BaseException as error:
            _record_error(span, error)
            raise


def record_status(span, status_code: int) -> None:
    """Record a client call's response status; a server error (5xx) fails the span.

    A 4xx is an answer the caller handles (a missing artifact, an expired handle).
    """
    if not span.is_recording():
        return
    span.set_attribute("http.response.status_code", status_code)
    if status_code >= 500:
        span.set_attribute("error.type", str(status_code))
        span.set_status(Status(StatusCode.ERROR))


@contextmanager
def linked_root_span(name: str, traceparent: Optional[str], attributes: dict) -> Iterator[object]:
    """A new trace's root span, linked to the span ``traceparent`` names when it is valid.

    A grading attempt runs long after the request that accepted its submission,
    and may be retried hours later: each attempt is its own bounded trace that
    points back at the acceptance. An error that escapes is recorded by its type only.
    """
    links = []
    if traceparent:
        linked = trace.get_current_span(_W3C.extract({"traceparent": traceparent})).get_span_context()
        if linked.is_valid:
            links.append(Link(linked))
    # An empty context: never a child of whatever is current in the worker task.
    with _tracer.start_as_current_span(name, context=Context(), kind=SpanKind.INTERNAL, links=links,
                                       attributes=attributes, record_exception=False,
                                       set_status_on_exception=False) as span:
        try:
            yield span
        except BaseException as error:
            _record_error(span, error)
            raise
