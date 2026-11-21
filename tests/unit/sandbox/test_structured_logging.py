"""Structured logs of the sandbox manager: one JSON schema, no secrets, correlated ids (#487)."""
import io
import json
import logging
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
import uvicorn.importer
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autograder.models.language import Language
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.remote_client import RemoteSandboxContainer, RemoteSandboxError, RemoteSandboxManager
from sandbox_manager.structured_logging import (
    REQUEST_DUMPING_LOGGERS, REQUEST_ID_HEADER, UNMATCHED_PATH, JSONFormatter, _ServiceHandler, accept_request_id,
    get_request_id, request_logging_middleware, reset_request_id, set_request_id, setup_logging,
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


def test_setup_keeps_foreign_handlers_replaces_its_own_and_silences_request_dumping_loggers():
    foreign = logging.NullHandler()
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        for _ in range(2):
            setup_logging(json_logs=True, service_name="s", app_env="e", log_level="DEBUG")
        assert foreign in root.handlers
        assert len([h for h in root.handlers if isinstance(h, _ServiceHandler)]) == 1
        assert logging.getLogger("uvicorn.access").disabled
        assert logging.getLogger("uvicorn.error").propagate
        # Even at DEBUG: URLs (handles), AI request bodies (student code), signed S3 headers.
        assert {"urllib3", "httpx", "openai", "botocore"} <= set(REQUEST_DUMPING_LOGGERS)
        assert not any(logging.getLogger(name).isEnabledFor(logging.INFO) for name in REQUEST_DUMPING_LOGGERS)
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


def json_stream():
    """Point the service handler at a fresh stream and return a reader of its JSON lines."""
    stream = io.StringIO()
    for handler in logging.getLogger().handlers:
        if isinstance(handler, _ServiceHandler):
            handler.setStream(stream)
    return lambda: (stream.getvalue(), [json.loads(line) for line in stream.getvalue().splitlines()])


def test_a_failed_request_logs_its_template_and_resets_the_request_id():
    setup_logging(json_logs=True, service_name="s", app_env="e")
    lines = json_stream()
    app = FastAPI()
    app.middleware("http")(request_logging_middleware)

    @app.get("/things/{secret}")
    def explode(secret: str):
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/things/handle-xyz", headers={REQUEST_ID_HEADER: "req-9"}).status_code == 500
    out, records = lines()
    assert "handle-xyz" not in out
    [failed] = [r for r in records if r["message"] == "http_request_failed"]
    assert failed["path"] == "/things/{secret}" and failed["status"] == 500 and failed["request_id"] == "req-9"
    assert failed["logger"] == "http.request" and "RuntimeError: boom" in failed["exception"]
    assert get_request_id() is None


def test_a_logged_transport_failure_carries_no_handle():
    sandbox = RemoteSandboxContainer("handle-secret-1", Language.PYTHON, "http://sandbox:8001", token="tok")
    sandbox._session.send = Mock(side_effect=requests.ConnectionError(  # pylint: disable=protected-access
        "Max retries exceeded with url: /sandboxes/handle-secret-1/prepare"))
    setup_logging(json_logs=True, service_name="s", app_env="e")
    lines = json_stream()
    try:
        sandbox.prepare_workdir({})
    except RemoteSandboxError:
        logging.getLogger("test").exception("Execution session cleanup failed")
    out, records = lines()
    assert "RemoteSandboxError" in records[0]["exception"] and "handle-secret-1" not in out


def test_logging_settings_come_from_the_environment(monkeypatch):
    for name in ("JSON_LOGS", "LOG_LEVEL", "SERVICE_NAME", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)
    defaults = ControlSettings.from_env()
    assert (defaults.json_logs, defaults.log_level, defaults.service_name, defaults.app_env) == (
        False, "INFO", "autograder-sandbox-manager", "local")
    monkeypatch.setenv("JSON_LOGS", "true")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("SERVICE_NAME", "sbx")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SANDBOX_API_TOKEN", "t")
    configured = ControlSettings.from_env()
    assert (configured.json_logs, configured.log_level, configured.service_name, configured.app_env) == (
        True, "warning", "sbx", "staging")
    configured.validate()
    with pytest.raises(RuntimeError, match="LOG_LEVEL"):
        ControlSettings(token="t", log_level="LOUD").validate()


def test_the_image_starts_the_sandbox_manager_as_a_factory():
    dockerfile = (Path(__file__).resolve().parents[3] / "Dockerfile.sandbox").read_text(encoding="utf-8")
    command = json.loads(re.search(r"^CMD (\[.*\])$", dockerfile, re.MULTILINE).group(1))
    target = command[command.index("--factory") + 1]
    assert uvicorn.importer.import_from_string(target) is create_app
