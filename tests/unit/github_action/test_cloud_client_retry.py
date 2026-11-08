# pylint: disable=missing-function-docstring,missing-class-docstring,invalid-name,protected-access
"""INT-04 client retry contract: bounded, idempotent, deadline-aware and honest."""
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import shutil
import socket
import ssl
import subprocess
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

    def respond(request, *, connect_timeout, read_timeout, **kwargs):
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


# --- absolute deadline across headers and body (review on #399) ---------------------------


class _DripServer:
    """Accept one request at a time and answer with `chunks`, sleeping between them."""

    def __init__(self, chunks, interval):
        self.chunks, self.interval = chunks, interval
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.url = f"http://127.0.0.1:{self.listener.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self._drip, args=(connection,), daemon=True).start()

    def _drip(self, connection):
        with connection:
            try:
                connection.recv(65536)
                for chunk in self.chunks:
                    connection.sendall(chunk)
                    time.sleep(self.interval)
            except OSError:
                pass  # the client gave up

    def close(self):
        self.listener.close()


def _bytes(text):
    return [bytes([value]) for value in text.encode()]


def _assert_bounded(chunks, call, *, budget=0.1, limit=0.6):
    server = _DripServer(chunks, 0.04)
    started = time.monotonic()
    try:
        with pytest.raises((CloudConnectionError, CloudClientError)) as error:
            call(CloudClient(server.url, "t", connect_timeout=budget, read_timeout=budget,
                             total_timeout=budget, max_retries=0))
    finally:
        server.close()
    assert time.monotonic() - started < limit
    return error.value


def test_slow_drip_body_cannot_outlive_the_total_deadline():
    # The reviewer's reproduction: 8 bytes of {"id":1} at 40 ms intervals.
    head = [b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 8\r\n\r\n"]
    error = _assert_bounded(head + _bytes('{"id":1}'), lambda client: client.get_grading_config(1))
    assert isinstance(error, CloudConnectionError)


def test_close_delimited_body_is_not_accepted_truncated():
    head = [b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n"]
    error = _assert_bounded(head + _bytes('{"submission_id": 12345}'),
                            lambda client: client.submit_external_result({}, idempotency_key="k"))
    # Without the watchdog check this returned a truncated body as success.
    assert isinstance(error, CloudConnectionError) and error.uncertain is True
    assert isinstance(error.__cause__, TimeoutError)


def test_a_read_cut_by_the_deadline_reports_the_deadline_whatever_the_socket_raised():
    """The watchdog's shutdown can surface as a reset or a plain OSError instead of EOF; either way the
    deadline ended the exchange, and the failure says so (the race behind a flaky CI run)."""
    def cut_at_the_deadline(_req, *, watchdog, **_kwargs):
        while not watchdog.expired:
            time.sleep(0.005)
        raise ConnectionResetError(104, "Connection reset by peer")

    with patch.object(cloud_client, "_urlopen", side_effect=cut_at_the_deadline):
        with pytest.raises(CloudConnectionError) as error:
            CloudClient("http://cloud.invalid", "t", connect_timeout=0.05, read_timeout=0.05,
                        total_timeout=0.05, max_retries=0).submit_external_result({}, idempotency_key="k")
    assert error.value.uncertain is True
    assert isinstance(error.value.__cause__, TimeoutError)
    assert isinstance(error.value.__cause__.__cause__, ConnectionResetError)  # the socket's report is kept


def test_trickled_headers_are_bounded():
    _assert_bounded(_bytes("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"),
                    lambda client: client.get_grading_config(1))


def test_trickled_error_body_is_bounded():
    head = [b"HTTP/1.1 409 Conflict\r\nContent-Type: application/json\r\nContent-Length: 80\r\n\r\n"]
    error = _assert_bounded(head + _bytes('{"detail": {"code": "IDEMPOTENCY_KEY_REUSED", "message": "x"}}' + " " * 20),
                            lambda client: client.submit_external_result({}, idempotency_key="k"))
    # The permanent status is still reported; the unread detail is simply omitted.
    assert isinstance(error, CloudClientError) and error.status_code == 409


def test_fast_response_within_deadline_is_unaffected():
    head = [b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 8\r\n\r\n{\"id\":1}"]
    server = _DripServer(head, 0)
    try:
        assert CloudClient(server.url, "t", total_timeout=5).get_grading_config(1) == {"id": 1}
    finally:
        server.close()


def test_stalled_tls_handshake_is_bounded_by_the_total_deadline():
    listener = socket.socket()  # accepts TCP but never answers the ClientHello
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    started = time.monotonic()
    try:
        with pytest.raises(CloudConnectionError):
            CloudClient(f"https://127.0.0.1:{listener.getsockname()[1]}", "t", connect_timeout=5,
                        read_timeout=5, total_timeout=0.3, max_retries=0).get_grading_config(1)
    finally:
        listener.close()
    assert time.monotonic() - started < 1.5


def test_real_tls_exchange_verifies_certificate_and_succeeds(tmp_path, monkeypatch):
    if shutil.which("openssl") is None:
        pytest.skip("openssl is required to create a test certificate")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = b'{"id": 7}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"https://127.0.0.1:{server.server_address[1]}"
    try:
        # Untrusted certificate: verification is still enforced (permanent, no retry needed).
        with pytest.raises(CloudConnectionError):
            CloudClient(url, "t", max_retries=0).get_grading_config(7)
        monkeypatch.setenv("SSL_CERT_FILE", str(cert))
        assert CloudClient(url, "t", total_timeout=5).get_grading_config(7) == {"id": 7}
    finally:
        server.shutdown()
        server.server_close()
