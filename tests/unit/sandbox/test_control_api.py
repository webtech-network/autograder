"""Private control API over HTTP (TestClient): authentication, ownership, errors, recovery."""
import secrets

import pytest
from fastapi.testclient import TestClient

from sandbox_manager.api import create_app
from sandbox_manager.models.sandbox_models import SandboxState
from tests.unit.sandbox.fakes import FakeManager

TOKEN = "control-token-" + "x" * 20


def lease_headers(secret=None, token=TOKEN):
    return {"Authorization": f"Bearer {token}", "X-Sandbox-Lease": secret or secrets.token_urlsafe(32)}


@pytest.fixture
def manager():
    return FakeManager(lease_seconds=60)


@pytest.fixture
def client(manager):
    with TestClient(create_app(token=TOKEN, manager_factory=lambda: manager, max_body_bytes=4096)) as test_client:
        yield test_client


def acquire(client, secret=None):
    headers = lease_headers(secret)
    response = client.post("/sandboxes/python", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["sandbox_id"], headers


def code(response):
    return response.json()["detail"]["code"]


def test_startup_requires_a_token(monkeypatch):
    monkeypatch.delenv("SANDBOX_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="SANDBOX_API_TOKEN"):
        with TestClient(create_app(manager_factory=FakeManager)):
            pass


def test_health_is_open_but_everything_else_requires_the_token(client):
    assert client.get("/health").status_code == 200
    assert code(client.get("/stats")) == "unauthorized"
    assert client.get("/stats", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    response = client.post("/sandboxes/python", headers=lease_headers(token="wrong"))
    assert response.status_code == 401 and code(response) == "unauthorized"
    response = client.post("/sandboxes/python", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 401 and code(response) == "lease_required"


def test_another_client_cannot_operate_or_dispose_a_foreign_lease(client, manager):
    handle, owner = acquire(client)
    intruder = lease_headers()  # authenticated host, different lease secret
    for method, path, body in (("post", "/process", {"argv": ["id"]}), ("post", "/prepare", {"submission_files": {}}),
                               ("get", "/files?path=/app/a", None), ("delete", "", None)):
        kwargs = {"headers": intruder} | ({"json": body} if body is not None else {})
        response = getattr(client, method)(f"/sandboxes/{handle}{path}", **kwargs)
        assert response.status_code == 404 and code(response) == "sandbox_not_found", (path, response.text)
    sandbox = manager.leased[0]
    assert sandbox.runs == [] and sandbox.state is SandboxState.BUSY
    assert client.post(f"/sandboxes/{handle}/process", headers=owner, json={"argv": ["id"]}).status_code == 200


def test_handles_are_opaque_not_container_ids(client, manager):
    handle, _ = acquire(client)
    other, _ = acquire(client)
    assert handle != other and len(handle) == 32


def test_distinct_errors_for_unknown_expired_missing_artifact_and_execution_failure(client, manager):
    handle, headers = acquire(client)
    unknown = client.post("/sandboxes/" + "0" * 32 + "/process", headers=headers, json={"argv": ["id"]})
    assert (unknown.status_code, code(unknown)) == (404, "sandbox_not_found")

    missing = client.get(f"/sandboxes/{handle}/files", headers=headers, params={"path": "/app/output.txt"})
    assert (missing.status_code, code(missing)) == (404, "artifact_not_found")

    failed = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["explode"]})
    assert (failed.status_code, code(failed)) == (500, "execution_failed")
    assert "docker exec failed" not in failed.text  # internal detail stays in server logs

    too_long = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["id"], "timeout": 61})
    assert (too_long.status_code, code(too_long)) == (422, "invalid_request")
    huge = client.get(f"/sandboxes/{handle}/files", headers=headers, params={"path": "/app/x", "max_bytes": 10**9})
    assert (huge.status_code, code(huge)) == (422, "invalid_request")

    manager.leased[0].state = SandboxState.STOPPED  # the pool expired the lease
    expired = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["id"]})
    assert (expired.status_code, code(expired)) == (410, "sandbox_expired")
    # Disposal of an expired lease is confirmed, not an error.
    assert client.delete(f"/sandboxes/{handle}", headers=headers).json() == {"state": "disposed"}


def test_replayed_acquisition_returns_the_same_handle(client, manager):
    secret = secrets.token_urlsafe(32)
    first, _ = acquire(client, secret)
    second, _ = acquire(client, secret)
    assert first == second and len(manager.leased) == 1


def test_disposal_is_idempotent_and_survives_a_lost_response(client, manager):
    handle, headers = acquire(client)
    assert client.delete(f"/sandboxes/{handle}", headers=headers).json() == {"state": "disposed"}
    # The client never saw that response and retries: the closure is confirmed again.
    again = client.delete(f"/sandboxes/{handle}", headers=headers)
    assert (again.status_code, again.json()) == (200, {"state": "disposed"})
    assert manager.dispose_calls == 1
    after = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["id"]})
    assert (after.status_code, code(after)) == (410, "sandbox_expired")


def test_failed_disposal_keeps_a_closing_record_until_confirmed(client, manager):
    handle, headers = acquire(client)
    manager.dispose_failures = 1
    first = client.delete(f"/sandboxes/{handle}", headers=headers)
    assert (first.status_code, first.json()) == (202, {"state": "closing"})
    stats = client.get("/stats", headers=headers).json()
    assert stats["handles"]["closing"] == 1 and stats["cleanup_problems"]
    blocked = client.post(f"/sandboxes/{handle}/process", headers=headers, json={"argv": ["id"]})
    assert (blocked.status_code, code(blocked)) == (410, "sandbox_expired")
    retry = client.delete(f"/sandboxes/{handle}", headers=headers)
    assert (retry.status_code, retry.json()) == (200, {"state": "disposed"})
    assert client.get("/stats", headers=headers).json()["handles"] == {"active": 0, "closing": 0, "tombstones": 1}


def test_capacity_and_body_limits(client, manager):
    manager.capacity = 1
    acquire(client)
    full = client.post("/sandboxes/python", headers=lease_headers())
    assert (full.status_code, code(full)) == (503, "capacity_unavailable")
    assert client.get("/stats", headers=lease_headers()).json()["handles"]["active"] == 1
    body = b'{"submission_files": {"a": {"filename": "a", "content": "' + b"x" * 5000 + b'"}}}'
    declared = client.post("/sandboxes/abc/prepare", headers=lease_headers(), content=body)
    assert (declared.status_code, code(declared)) == (413, "request_too_large")

    def chunks():  # no Content-Length: the limit is enforced on received bytes
        yield body[:3000]
        yield body[3000:]
    streamed = client.post("/sandboxes/abc/prepare", headers=lease_headers(), content=chunks())
    assert (streamed.status_code, code(streamed)) == (413, "request_too_large")


def test_shutdown_disposes_open_handles_and_the_manager(manager):
    with TestClient(create_app(token=TOKEN, manager_factory=lambda: manager)) as test_client:
        acquire(test_client)
        acquire(test_client)
    assert manager.started and manager.shut_down
    assert all(item.state is SandboxState.STOPPED for item in manager.leased)
