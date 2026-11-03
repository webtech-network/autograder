"""INT-04 client retry contract: bounded, idempotent, deadline-aware and honest."""
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import socket
import threading
import time
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from github_action import cloud_client
from github_action.cloud_client import CloudClient, CloudClientError, CloudConnectionError, _retry_after


def http_error(code, body=None, headers=None):
    raw = json.dumps(body).encode() if body is not None else b""
    return urllib.error.HTTPError("https://cloud.invalid", code, f"HTTP {code}", headers or {}, BytesIO(raw))


def ok(body):
    response = MagicMock()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    response.read.return_value = json.dumps(body).encode()
    return response


def client(**kwargs):
    return CloudClient("https://cloud.invalid", "never-log-me", **kwargs)


@pytest.mark.parametrize("failure", [
    http_error(503), http_error(429), http_error(502), http_error(504), http_error(500), http_error(408),
    urllib.error.URLError(ConnectionResetError("reset")), TimeoutError("read timed out"),
])
def test_keyed_post_retries_transient_failures_with_the_same_key(failure):
    sent = []

    def respond(request, **kwargs):
        sent.append(request.get_header("Idempotency-key"))
        if len(sent) == 1:
            raise failure
        return ok({"submission_id": 9})

    with patch.object(cloud_client, "_urlopen", side_effect=respond), patch("time.sleep"):
        assert client().submit_external_result({"outcome": {}}, idempotency_key="k-1") == {"submission_id": 9}
    assert sent == ["k-1", "k-1"]


def test_unkeyed_post_is_sent_once():
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(503)) as request, patch("time.sleep") as sleep:
        with pytest.raises(CloudConnectionError) as error:
            client().submit_external_result({"outcome": {}})
    assert request.call_count == 1
    sleep.assert_not_called()
    assert error.value.uncertain is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 413, 422])
def test_permanent_errors_are_not_retried(status):
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(status)) as request, patch("time.sleep"):
        with pytest.raises(CloudClientError) as error:
            client().submit_external_result({}, idempotency_key="k")
    assert request.call_count == 1
    assert error.value.status_code == status
    assert "never-log-me" not in str(error.value)


def test_conflict_preserves_safe_structured_detail():
    body = {"detail": {"code": "IDEMPOTENCY_KEY_REUSED",
                       "message": "This Idempotency-Key was already used with a different request"}}
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(409, body)):
        with pytest.raises(CloudClientError) as error:
            client().submit_external_result({}, idempotency_key="k")
    assert error.value.code == "IDEMPOTENCY_KEY_REUSED"
    assert "already used" in error.value.detail
    assert "IDEMPOTENCY_KEY_REUSED" in str(error.value)


def test_validation_detail_lists_paths_without_values():
    body = {"detail": [{"path": ["body", "outcome", "score"], "code": "x", "message": "must be finite"}]}
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(422, body)):
        with pytest.raises(CloudClientError) as error:
            client().submit_external_result({}, idempotency_key="k")
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.detail == "body.outcome.score: must be finite"


def test_long_detail_is_truncated():
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(403, {"detail": "x" * 1000})):
        with pytest.raises(CloudClientError) as error:
            client().get_grading_config(1)
    assert len(error.value.detail) == 300


def test_retry_after_seconds_is_honoured():
    delays = []
    failures = [http_error(429, headers={"Retry-After": "7"})]

    def respond(request, **kwargs):
        if failures:
            raise failures.pop()
        return ok({})

    with patch.object(cloud_client, "_urlopen", side_effect=respond), patch("time.sleep", side_effect=delays.append):
        client().submit_external_result({}, idempotency_key="k")
    assert delays == [7.0]


def test_retry_after_is_capped():
    delays = []
    failures = [http_error(503, headers={"Retry-After": "3600"})]

    def respond(request, **kwargs):
        if failures:
            raise failures.pop()
        return ok({})

    with patch.object(cloud_client, "_urlopen", side_effect=respond), patch("time.sleep", side_effect=delays.append):
        client(total_timeout=600).submit_external_result({}, idempotency_key="k")
    assert delays == [30.0]


def test_retry_after_http_date():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    later = format_datetime(now + timedelta(seconds=12), usegmt=True)
    assert _retry_after({"Retry-After": later}, now=now.timestamp()) == pytest.approx(12)
    assert _retry_after({"Retry-After": format_datetime(now - timedelta(seconds=5), usegmt=True)},
                        now=now.timestamp()) == 0
    assert _retry_after({"Retry-After": "soon"}) is None
    assert _retry_after({}) is None


def test_retry_that_would_pass_the_total_deadline_is_not_attempted():
    with patch.object(cloud_client, "_urlopen", side_effect=http_error(503, headers={"Retry-After": "20"})) as request, \
            patch("time.sleep") as sleep:
        with pytest.raises(CloudConnectionError) as error:
            client(total_timeout=5).submit_external_result({}, idempotency_key="k")
    assert request.call_count == 1
    sleep.assert_not_called()
    assert error.value.status_code == 503


def test_total_deadline_bounds_attempts_and_per_request_timeouts():
    clock = [100.0]
    seen = []

    def respond(request, *, connect_timeout, read_timeout):
        seen.append((connect_timeout, read_timeout))
        clock[0] += 4
        raise urllib.error.URLError(ConnectionResetError("reset"))

    with patch.object(cloud_client, "_urlopen", side_effect=respond), \
            patch("time.monotonic", side_effect=lambda: clock[0]), \
            patch("time.sleep", side_effect=lambda delay: clock.__setitem__(0, clock[0] + delay)), \
            patch("random.random", return_value=0.0):
        with pytest.raises(CloudConnectionError):
            client(connect_timeout=10, read_timeout=30, total_timeout=9, max_retries=10).get_grading_config(1)
    # Every attempt is clamped to the remaining budget and attempts stop at the deadline.
    assert seen[0] == (9, 9)
    assert all(connect <= 9 and read <= 9 for connect, read in seen)
    assert len(seen) <= 3


def test_get_retries_without_a_key_and_is_never_uncertain():
    with patch.object(cloud_client, "_urlopen", side_effect=urllib.error.URLError("down")) as request, patch("time.sleep"):
        with pytest.raises(CloudConnectionError) as error:
            client(max_retries=2).get_grading_config(1)
    assert request.call_count == 3
    assert error.value.uncertain is False


def test_refused_connection_is_a_definite_failure_for_posts():
    with patch.object(cloud_client, "_urlopen", side_effect=urllib.error.URLError(ConnectionRefusedError())), \
            patch("time.sleep"):
        with pytest.raises(CloudConnectionError) as error:
            client(max_retries=1).submit_external_result({}, idempotency_key="k")
    assert error.value.uncertain is False
    assert "reachable" in str(error.value)


def test_lost_post_response_is_reported_as_uncertain():
    with patch.object(cloud_client, "_urlopen", side_effect=urllib.error.URLError(ConnectionResetError())), \
            patch("time.sleep"):
        with pytest.raises(CloudConnectionError) as error:
            client(max_retries=1).submit_external_result({}, idempotency_key="k")
    assert error.value.uncertain is True
    assert "same Idempotency-Key" in str(error.value)
    assert "never-log-me" not in str(error.value)


@pytest.mark.parametrize("kwargs", [{"connect_timeout": 0}, {"read_timeout": -1}, {"total_timeout": 0},
                                    {"max_retries": -1}])
def test_invalid_timeouts_are_rejected(kwargs):
    with pytest.raises(ValueError):
        client(**kwargs)


# --- real sockets: the configured deadlines are the applied deadlines ---------------------


def test_connect_timeout_is_applied_to_connection_and_read_timeout_afterwards():
    applied = {}
    real_create = socket.create_connection
    real_connect = cloud_client._DeadlineConnection.connect

    def record(address, timeout=None, source_address=None, **kwargs):
        applied["connect"] = timeout
        return real_create(address, timeout=timeout, source_address=source_address)

    def connect(self):
        real_connect(self)
        applied["read"] = self.sock.gettimeout()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = b'{"id": 1}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with patch("socket.create_connection", side_effect=record), \
                patch.object(cloud_client._DeadlineConnection, "connect", connect):
            result = CloudClient(f"http://127.0.0.1:{server.server_address[1]}", "t", connect_timeout=1.5,
                                 read_timeout=4.5).get_grading_config(1)
        server.shutdown()
    assert result == {"id": 1}
    assert applied == {"connect": 1.5, "read": 4.5}


def test_read_timeout_bounds_a_silent_server():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    accepted = []
    thread = threading.Thread(target=lambda: accepted.append(listener.accept()), daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with pytest.raises(CloudConnectionError) as error:
            CloudClient(f"http://127.0.0.1:{listener.getsockname()[1]}", "t", connect_timeout=5,
                        read_timeout=0.3, max_retries=0).submit_external_result({}, idempotency_key="k")
    finally:
        listener.close()
    assert time.monotonic() - started < 3
    assert error.value.uncertain is True


def test_real_server_transient_failures_then_receipt():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            calls.append(self.headers["Idempotency-Key"])
            status, body = (503, b"{}") if len(calls) < 3 else (200, b'{"submission_id": 5}')
            self.send_response(status)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        receipt = CloudClient(f"http://127.0.0.1:{server.server_address[1]}", "t").submit_external_result(
            {"outcome": {}}, idempotency_key="same")
        server.shutdown()
    assert receipt == {"submission_id": 5}
    assert calls == ["same", "same", "same"]
