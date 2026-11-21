"""Structured logs of the sandbox manager: one JSON schema, no secrets, correlated ids (#487)."""
import io
import json
import logging
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from autograder.models.language import Language
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.remote_client import RemoteSandboxManager
from sandbox_manager.structured_logging import (
    HTTP_CLIENT_LOGGERS, REQUEST_ID_HEADER, UNMATCHED_PATH, JSONFormatter, _ServiceHandler, accept_request_id, reset_request_id,
    set_request_id, setup_logging,
)
from tests.unit.sandbox.test_control_api import AUTH, TOKEN, FakeManager, acquire
from tests.unit.sandbox.test_remote_client import acquired


@pytest.fixture(autouse=True)
def restore_logging():
    """Remove the service handler afterwards (its stream belongs to one test)."""
    yield
    root = logging.getLogger()
    for handler in [h for h in root.handlers if isinstance(h, _ServiceHandler)]:
        root.removeHandler(handler)


@pytest.fixture
def logged():
    """A JSON-logging control API and a reader of the JSON lines it wrote."""
    manager = FakeManager()
    settings = ControlSettings(token=TOKEN, json_logs=True, app_env="staging", reaper_interval_seconds=3600)
    with TestClient(create_app(settings, lambda: manager)) as client:
        stream = io.StringIO()
        for handler in logging.getLogger().handlers:
            if isinstance(handler, _ServiceHandler):
                handler.setStream(stream)

        def lines():
            out = stream.getvalue()
            return out, [json.loads(line) for line in out.splitlines()]
        yield client, lines


def request_lines(records):
    return [r for r in records if r["message"] in ("http_request_completed", "http_request_failed")]


def record(**extra):
    item = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    for name, value in extra.items():
        setattr(item, name, value)
    return item


def test_json_lines_share_the_api_schema_and_omit_absent_trace_fields():
    line = json.loads(JSONFormatter("autograder-sandbox-manager", "production").format(record(request_id="r-1")))
    assert line["message"] == "hello world" and line["level"] == "INFO" and line["logger"] == "x"
    assert line["service"] == "autograder-sandbox-manager" and line["env"] == "production"
    assert line["request_id"] == "r-1" and "timestamp" in line
    assert "trace_id" not in line and "span_id" not in line

    traced = json.loads(JSONFormatter("s", "e").format(record(trace_id="a" * 32, span_id="b" * 16)))
    assert traced["trace_id"] == "a" * 32 and traced["span_id"] == "b" * 16


@pytest.mark.parametrize("value", ["", "  ", "a" * 129, "bad id", "line\nbreak", "x\"}{", "ünïcode"])
def test_malformed_incoming_request_ids_are_replaced(value):
    replaced = accept_request_id(value)
    assert replaced != value and len(replaced) == 32


@pytest.mark.parametrize("value", ["abc", "0f8f-1a2b", "req.1:2_3", "a" * 128])
def test_well_formed_incoming_request_ids_are_kept(value):
    assert accept_request_id(value) == value


def test_setup_keeps_foreign_handlers_replaces_its_own_and_silences_url_bearing_loggers():
    foreign = logging.NullHandler()
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        for _ in range(2):
            setup_logging(json_logs=True, service_name="s", app_env="e")
        assert foreign in root.handlers
        assert len([h for h in root.handlers if isinstance(h, _ServiceHandler)]) == 1
        assert logging.getLogger("uvicorn.access").disabled
        assert logging.getLogger("uvicorn.error").propagate
        assert all(logging.getLogger(name).level == logging.WARNING for name in HTTP_CLIENT_LOGGERS)
    finally:
        root.removeHandler(foreign)


def test_request_lines_log_the_route_template_never_the_handle_or_token(logged):
    client, lines = logged
    handle = acquire(client).json()["sandbox_id"]
    response = client.post(f"/sandboxes/{handle}/process?probe=secret-query", headers=AUTH,
                           json={"argv": ["python", "main.py"], "timeout": 5})
    assert response.status_code == 200
    out, records = lines()
    assert handle not in out and TOKEN not in out and "secret-query" not in out and "127.0.0.1" not in out
    assert "testclient" not in out  # the client address (TestClient's host) is never logged
    process = [r for r in request_lines(records) if r["path"] == "/sandboxes/{sandbox_id}/process"]
    assert len(process) == 1
    assert process[0]["method"] == "POST" and process[0]["status"] == 200
    assert isinstance(process[0]["duration_ms"], int)
    assert process[0]["service"] == "autograder-sandbox-manager" and process[0]["env"] == "staging"


def test_an_unmatched_path_is_not_logged_raw(logged):
    client, lines = logged
    assert client.get("/sandboxes/some-handle-value/unknown/route", headers=AUTH).status_code == 404
    out, records = lines()
    assert "some-handle-value" not in out
    assert [r["path"] for r in request_lines(records)] == [UNMATCHED_PATH]


def test_request_id_is_kept_or_replaced_echoed_and_stamped_on_the_request_line(logged):
    client, lines = logged
    kept = client.get("/stats", headers={**AUTH, REQUEST_ID_HEADER: "api-req.42"})
    replaced = client.get("/stats", headers={**AUTH, REQUEST_ID_HEADER: "evil id"})
    assert kept.headers[REQUEST_ID_HEADER] == "api-req.42"
    fresh = replaced.headers[REQUEST_ID_HEADER]
    assert fresh != "evil id" and len(fresh) == 32
    _, records = lines()
    assert [r["request_id"] for r in request_lines(records)] == ["api-req.42", fresh]


def test_remote_client_forwards_the_active_request_id():
    manager = RemoteSandboxManager("http://sandbox:8001", token="tok")
    manager._session.send = Mock(return_value=acquired())  # pylint: disable=protected-access
    token = set_request_id("attempt-1")
    try:
        sandbox = manager.get_sandbox(Language.PYTHON)
        sandbox._session.send = Mock(return_value=acquired())  # pylint: disable=protected-access
        sandbox.prepare_workdir({})
    finally:
        reset_request_id(token)
    for session in (manager._session, sandbox._session):  # pylint: disable=protected-access
        sent = session.send.call_args.args[0]
        assert sent.headers[REQUEST_ID_HEADER] == "attempt-1" and sent.headers["Authorization"] == "Bearer tok"

    # Outside a request nothing is added.
    manager._session.send = Mock(return_value=acquired())  # pylint: disable=protected-access
    manager.get_pool_stats()
    assert REQUEST_ID_HEADER not in manager._session.send.call_args.args[0].headers  # pylint: disable=protected-access
