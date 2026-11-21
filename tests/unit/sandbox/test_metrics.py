"""Prometheus exposition of the sandbox control API and the shared HTTP middleware (#488)."""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from prometheus_client.parser import text_string_to_metric_families

from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.metrics import HttpMetrics, HttpMetricsMiddleware, SandboxCollector
from tests.unit.sandbox.fakes import Clock
from tests.unit.sandbox.test_control_api import AUTH, TOKEN, FakeManager


def pool(**counts):
    stats = {"idle": 0, "creating": 0, "active": 0, "closing": 0, "quarantined": 0, "pool_size": 2,
             "quarantine": [{"container_id": "abc123", "error": "secret detail"}], "language": "python"}
    return stats | counts


class StatsManager(FakeManager):
    def get_pool_stats(self):
        return {"python": pool(idle=2, active=1), "java": pool(quarantined=1, pool_size=0)}


def samples(text):
    """``{(name, frozenset(labels)): value}`` of a Prometheus text exposition."""
    return {(sample.name, frozenset(sample.labels.items())): sample.value
            for family in text_string_to_metric_families(text) for sample in family.samples}


@pytest.fixture
def instrumented():
    registry = CollectorRegistry()
    app = FastAPI()

    @app.get("/items/{item_id}")
    def item(item_id: str):
        return {"id": item_id}

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    app.add_middleware(HttpMetricsMiddleware, metrics=HttpMetrics(registry))
    return registry, TestClient(app, raise_server_exceptions=False)


def test_requests_are_labelled_by_route_template_never_by_concrete_path(instrumented):
    registry, client = instrumented
    for item_id in ("1", "2", "student-secret"):
        assert client.get(f"/items/{item_id}").status_code == 200
    assert client.get("/nowhere/at/all").status_code == 404
    labels = {"method": "GET", "route": "/items/{item_id}", "status": "200"}
    assert registry.get_sample_value("http_server_requests_total", labels) == 3
    assert registry.get_sample_value("http_server_requests_total",
                                     {"method": "GET", "route": "unmatched", "status": "404"}) == 1
    assert registry.get_sample_value("http_server_request_duration_seconds_count",
                                     {"method": "GET", "route": "/items/{item_id}"}) == 3
    exposed = "\n".join(str(metric.samples) for metric in registry.collect())
    assert "student-secret" not in exposed and "/nowhere" not in exposed


def test_an_unhandled_exception_counts_as_500_and_in_progress_returns_to_zero(instrumented):
    registry, client = instrumented
    assert client.get("/boom").status_code == 500
    assert registry.get_sample_value("http_server_requests_total",
                                     {"method": "GET", "route": "/boom", "status": "500"}) == 1
    assert registry.get_sample_value("http_server_requests_in_progress", {"method": "GET"}) == 0


def test_unknown_methods_collapse_into_one_label(instrumented):
    registry, client = instrumented
    client.request("BREW", "/items/1")
    client.request("PROPFIND", "/items/1")
    methods = {sample.labels["method"] for metric in registry.collect() if metric.name == "http_server_requests"
               for sample in metric.samples}
    assert methods == {"other"}


def test_sandbox_collector_reports_every_state_per_language_and_the_budget():
    registry = CollectorRegistry()
    manager = StatsManager()
    registry.register(SandboxCollector(lambda: manager))
    assert registry.get_sample_value("autograder_sandboxes", {"language": "python", "state": "idle"}) == 2
    assert registry.get_sample_value("autograder_sandboxes", {"language": "python", "state": "active"}) == 1
    assert registry.get_sample_value("autograder_sandboxes", {"language": "java", "state": "quarantined"}) == 1
    assert registry.get_sample_value("autograder_sandboxes", {"language": "java", "state": "closing"}) == 0
    assert registry.get_sample_value("autograder_sandbox_pool_target", {"language": "python"}) == 2
    assert registry.get_sample_value("autograder_sandbox_budget_limit") == 3
    assert registry.get_sample_value("autograder_sandbox_budget_held") == 0
    assert registry.get_sample_value("autograder_sandbox_budget_waiting") == 0


def test_sandbox_collector_without_a_manager_reports_nothing():
    registry = CollectorRegistry()
    registry.register(SandboxCollector(lambda: None))
    assert list(registry.collect()) == []


def test_control_api_metrics_are_public_and_carry_requests_and_pools():
    manager = StatsManager()
    settings = ControlSettings(token=TOKEN, handle_ttl_seconds=60, tombstone_seconds=600,
                               reaper_interval_seconds=3600)
    with TestClient(create_app(settings, lambda: manager, clock=Clock())) as client:
        acquired = client.post("/sandboxes/python", json={"request_id": "request-0001"}, headers=AUTH)
        assert acquired.status_code == 200
        assert client.post("/sandboxes/python", json={"request_id": "request-0002"}).status_code == 401
        response = client.get("/metrics")  # no token
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    values = samples(response.text)
    route = "/sandboxes/{language}"
    assert values[("http_server_requests_total",
                   frozenset({"method": "POST", "route": route, "status": "200"}.items()))] == 1
    assert values[("http_server_requests_total",
                   frozenset({"method": "POST", "route": route, "status": "401"}.items()))] == 1
    assert values[("autograder_sandboxes", frozenset({"language": "python", "state": "active"}.items()))] == 1
    # Handles, container ids and quarantine errors are never exposed.
    assert acquired.json()["sandbox_id"] not in response.text
    assert "abc123" not in response.text and "secret detail" not in response.text
    assert "/metrics" not in create_app(settings, lambda: manager).openapi()["paths"]


def test_only_a_started_local_docker_host_reports_its_pools():
    from execution_host.docker import DockerHost
    assert DockerHost(mode="remote", api_url="http://sandbox-manager:8001").local_manager() is None
    local = DockerHost(mode="local")
    assert local.local_manager() is None  # not started: the scrape starts nothing
    local._manager = manager = StatsManager()  # pylint: disable=protected-access  # stands in for start()
    assert local.local_manager() is manager


async def _drive(app, raises=None):
    """One request through the middleware around ``app``; asserts it re-raises ``raises``.

    Returns the registry and what reached the client.
    """
    registry = CollectorRegistry()
    middleware = HttpMetricsMiddleware(app, HttpMetrics(registry))
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}
    if raises is None:
        await middleware(scope, receive, send)
    else:
        with pytest.raises(raises):
            await middleware(scope, receive, send)
    return registry, sent


def _status(registry):
    return {sample.labels["status"]: sample.value for metric in registry.collect()
            if metric.name == "http_server_requests" for sample in metric.samples
            if sample.name == "http_server_requests_total"}


@pytest.mark.asyncio
async def test_a_request_without_a_response_or_cancelled_counts_as_client_closed():
    async def no_response(_scope, _receive, _send):
        return None

    async def cancelled(_scope, _receive, _send):
        raise asyncio.CancelledError

    for app, raises in ((no_response, None), (cancelled, asyncio.CancelledError)):
        registry, _ = await _drive(app, raises)
        assert _status(registry) == {"499": 1}
        assert registry.get_sample_value("http_server_requests_in_progress", {"method": "GET"}) == 0


@pytest.mark.asyncio
async def test_an_exception_after_the_response_started_keeps_the_sent_status():
    async def fails_mid_body(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("body failed")

    registry, sent = await _drive(fails_mid_body, RuntimeError)
    assert sent[0]["status"] == 200
    assert _status(registry) == {"200": 1}
