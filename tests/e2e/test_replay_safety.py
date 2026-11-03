"""INT-04 against a real API process and the real Action delivery client."""
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import threading
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import requests

from github_action import main as action_main
from github_action.cloud_client import CloudClient, CloudClientError, CloudConnectionError
from github_action.cloud_exporter import delivery_key
from tests.e2e.contracts import create_config, poll
from tests.e2e.test_external_results import attestation


class ResponseDroppingProxy:
    """Forward complete requests upstream but drop the first `drop` responses.

    This reproduces "the server committed but the client never saw the reply".
    """

    def __init__(self, upstream, drop):
        parts = urlsplit(upstream)
        self.upstream = (parts.hostname, parts.port)
        self.drop = drop
        self.forwarded = 0
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(16)
        self.url = f"http://127.0.0.1:{self.listener.getsockname()[1]}"
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    @staticmethod
    def _read_request(sock):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(65536)
            if not chunk:
                return data
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        length = 0
        for line in head.split(b"\r\n")[1:]:
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip())
        while len(body) < length:
            body += sock.recv(65536)
        # Ask upstream to close so its response is delimited by EOF.
        head = b"\r\n".join(line for line in head.split(b"\r\n")
                            if not line.lower().startswith(b"connection:")) + b"\r\nConnection: close"
        return head + b"\r\n\r\n" + body

    def _handle(self, client):
        with client:
            request = self._read_request(client)
            with socket.create_connection(self.upstream) as upstream:
                upstream.sendall(request)
                response = b""
                while chunk := upstream.recv(65536):
                    response += chunk
            self.forwarded += 1
            if self.forwarded <= self.drop:
                client.shutdown(socket.SHUT_RDWR)  # committed upstream, reply lost
                return
            client.sendall(response)

    def close(self):
        self.listener.close()


def _root(url):
    return url.removesuffix("/api/v1")


def _count(api_base_url, auth_headers, user):
    return len(requests.get(api_base_url + "/submissions/user/" + user, headers=auth_headers, timeout=5).json())


def _payload(config):
    payload = attestation(config)
    payload["external_user_id"] = "replay-" + uuid4().hex
    return payload


def test_lost_upload_acknowledgement_is_recovered_without_duplicate(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    payload = _payload(config)
    proxy = ResponseDroppingProxy(_root(api_base_url), drop=1)
    try:
        client = CloudClient(proxy.url, isolated_api["producer_token"], total_timeout=30)
        receipt = client.submit_external_result(payload, idempotency_key=delivery_key(payload))
    finally:
        proxy.close()
    assert proxy.forwarded == 2  # the first commit plus one replay
    assert _count(api_base_url, auth_headers, payload["external_user_id"]) == 1
    stored = poll(api_base_url, auth_headers, receipt["submission_id"])
    assert stored["outcome"] == payload["outcome"]


def test_exhausted_lost_acknowledgements_report_uncertain_then_retry_recovers(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    payload = _payload(config)
    proxy = ResponseDroppingProxy(_root(api_base_url), drop=100)
    try:
        client = CloudClient(proxy.url, isolated_api["producer_token"], max_retries=1, total_timeout=30)
        with pytest.raises(CloudConnectionError) as error:
            client.submit_external_result(payload, idempotency_key=delivery_key(payload))
    finally:
        proxy.close()
    assert error.value.uncertain is True
    assert _count(api_base_url, auth_headers, payload["external_user_id"]) == 1  # it was stored
    receipt = CloudClient(_root(api_base_url), isolated_api["producer_token"]).submit_external_result(
        payload, idempotency_key=delivery_key(payload))
    assert _count(api_base_url, auth_headers, payload["external_user_id"]) == 1
    assert poll(api_base_url, auth_headers, receipt["submission_id"])["outcome"] == payload["outcome"]


def test_concurrent_uploads_of_one_attempt_converge(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    payload = _payload(config)
    client = CloudClient(_root(api_base_url), isolated_api["producer_token"])
    with ThreadPoolExecutor(8) as pool:
        receipts = list(pool.map(lambda _: client.submit_external_result(
            payload, idempotency_key=delivery_key(payload)), range(8)))
    assert len({receipt["submission_id"] for receipt in receipts}) == 1
    assert _count(api_base_url, auth_headers, payload["external_user_id"]) == 1


def test_changed_payload_under_same_attempt_is_a_typed_conflict(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    payload = _payload(config)
    client = CloudClient(_root(api_base_url), isolated_api["producer_token"])
    client.submit_external_result(payload, idempotency_key=delivery_key(payload))
    tampered = json.loads(json.dumps(payload))
    tampered["submission_metadata"] = {"source": "tampered"}
    with pytest.raises(CloudClientError) as error:
        client.submit_external_result(tampered, idempotency_key=delivery_key(payload))
    assert error.value.status_code == 409 and error.value.code == "IDEMPOTENCY_KEY_REUSED"


def test_new_grading_attempt_is_a_new_attestation(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    first, second = _payload(config), attestation(config)
    second["external_user_id"] = first["external_user_id"]
    assert first["outcome"]["execution_id"] != second["outcome"]["execution_id"]
    client = CloudClient(_root(api_base_url), isolated_api["producer_token"])
    ids = {client.submit_external_result(p, idempotency_key=delivery_key(p))["submission_id"] for p in (first, second)}
    assert len(ids) == 2


def test_action_delivery_retry_cli_replays_against_real_server(api_base_url, auth_headers, isolated_api,
                                                               tmp_path, monkeypatch):
    config = create_config(api_base_url, auth_headers)
    payload = _payload(config)
    (tmp_path / "delivery.json").write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    args = ["--retry-delivery-path", "delivery.json", "--autograder-cloud-url", _root(api_base_url),
            "--autograder-cloud-token", isolated_api["producer_token"]]
    for _ in range(3):
        assert action_main.run(action_main.parser.parse_args(args)) is True
    outputs = (tmp_path / "outputs").read_text().splitlines()
    ids = {line for line in outputs if line.startswith("submission-id=")}
    assert len(ids) == 1
    assert outputs.count("delivery-status=delivered") == 3
    assert _count(api_base_url, auth_headers, payload["external_user_id"]) == 1


def test_http_acceptance_replay_returns_original_receipt(api_base_url, auth_headers):
    config = create_config(api_base_url, auth_headers)
    user = "replay-" + uuid4().hex
    body = {"external_assignment_id": config["external_assignment_id"], "external_user_id": user,
            "username": "student", "files": [{"filename": "main.py", "content": "import os"}]}
    headers = {**auth_headers, "Idempotency-Key": "prisma-" + uuid4().hex}
    with ThreadPoolExecutor(6) as pool:
        responses = list(pool.map(lambda _: requests.post(api_base_url + "/submissions", json=body,
                                                          headers=headers, timeout=10), range(6)))
    assert {response.status_code for response in responses} == {202}
    assert len({response.json()["id"] for response in responses}) == 1
    finished = poll(api_base_url, auth_headers, responses[0].json()["id"])
    replay = requests.post(api_base_url + "/submissions", json=body, headers=headers, timeout=10)
    assert replay.json()["id"] == finished["id"] and replay.json()["status"] == finished["status"]
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert _count(api_base_url, auth_headers, user) == 1
    changed = {**body, "files": [{"filename": "main.py", "content": "print(1)"}]}
    conflict = requests.post(api_base_url + "/submissions", json=changed, headers=headers, timeout=10)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
