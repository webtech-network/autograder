"""Prometheus exposition shared by the sandbox control API and the HTTP service.

Every label value comes from a closed set: an HTTP method from ``HTTP_METHODS``
(else ``other``, the one spelling for any value outside its set), the matched route *template* (never the concrete path; a
request no route matched is ``unmatched``), a status code, a language of
:class:`~autograder.models.language.Language` and a pool state. Identifiers,
paths, tokens and submission content never become labels.

Each application owns its :class:`~prometheus_client.CollectorRegistry`, so
several applications in one process (tests) never share series.
"""
from time import perf_counter
from typing import Callable, Iterable, Optional

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from fastapi import Response

OTHER = "other"
#: Recorded when the client went away before a response started (nginx's convention).
CLIENT_CLOSED = 499
HTTP_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
UNMATCHED_ROUTE = "unmatched"
#: Seconds; control-API calls and API requests are sub-second, a capacity wait may take minutes.
HTTP_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
#: Pool states reported by ``LanguagePool.get_stats``.
SANDBOX_STATES = ("idle", "creating", "active", "closing", "quarantined")


def _method(scope) -> str:
    method = scope.get("method", "")
    return method if method in HTTP_METHODS else OTHER


def _route(scope) -> str:
    """The template of the route that handled the request (set by FastAPI's router)."""
    route = scope.get("route")
    return getattr(route, "path", None) or UNMATCHED_ROUTE


class HttpMetrics:
    """HTTP golden signals: rate, errors (by status) and duration per route template."""

    def __init__(self, registry: CollectorRegistry):
        self.requests = Counter("http_server_requests", "HTTP requests answered, by route template and status.",
                                ("method", "route", "status"), registry=registry)
        self.duration = Histogram("http_server_request_duration_seconds",
                                  "Time from receiving a request to the end of its response.",
                                  ("method", "route"), buckets=HTTP_BUCKETS, registry=registry)
        self.in_progress = Gauge("http_server_requests_in_progress", "HTTP requests being answered now.",
                                 ("method",), registry=registry)


class HttpMetricsMiddleware:
    """Pure ASGI middleware recording :class:`HttpMetrics` for every HTTP request.

    Register it outermost so rejections by other middleware count too. A request
    that raises before responding is recorded as status 500, one cancelled or
    finished without a response (the client disconnected) as 499; exceptions
    propagate unchanged.
    """

    def __init__(self, app, metrics: HttpMetrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = _method(scope)
        status = None

        async def send_and_record_status(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        in_progress = self.metrics.in_progress.labels(method)
        in_progress.inc()
        start = perf_counter()
        try:
            await self.app(scope, receive, send_and_record_status)
        except Exception:
            # Cancellation (a disconnected client) is not an Exception: it stays 499 below.
            status = status or 500
            raise
        finally:
            route = _route(scope)
            self.metrics.duration.labels(method, route).observe(perf_counter() - start)
            self.metrics.requests.labels(method, route, str(status or CLIENT_CLOSED)).inc()
            in_progress.dec()


class SandboxCollector(Collector):
    """Pool and budget gauges read from a sandbox manager at scrape time.

    ``manager`` returns the manager to read (``None`` before it exists, which
    yields no samples); it must offer ``get_pool_stats`` and ``get_budget_stats``.
    """

    def __init__(self, manager: Callable[[], Optional[object]]):
        self._manager = manager

    def describe(self) -> Iterable:
        return []  # Nothing is read at registration.

    def collect(self):
        manager = self._manager()
        if manager is None:
            return
        sandboxes = GaugeMetricFamily("autograder_sandboxes", "Sandbox containers by language and pool state.",
                                      labels=("language", "state"))
        warm = GaugeMetricFamily("autograder_sandbox_pool_target",
                                 "Idle sandboxes each language pool keeps warm (pool_size).", labels=("language",))
        for language, stats in sorted(manager.get_pool_stats().items()):
            for state in SANDBOX_STATES:
                sandboxes.add_metric((language, state), stats[state])
            warm.add_metric((language,), stats["pool_size"])
        budget = manager.get_budget_stats()
        yield sandboxes
        yield warm
        yield GaugeMetricFamily("autograder_sandbox_budget_limit",
                                "Host sandbox budget (max_sandboxes): non-idle sandboxes it may hold at once.",
                                value=budget["max_sandboxes"])
        yield GaugeMetricFamily("autograder_sandbox_budget_held", "Budget slots held now.", value=budget["held"])
        yield GaugeMetricFamily("autograder_sandbox_budget_waiting",
                                "Acquisitions waiting for a budget slot.", value=budget["waiting"])


def exposition(registry: CollectorRegistry) -> Response:
    """The registry in the Prometheus text format."""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
