"""INT-01: every HTTP route and alias is covered by one declared trust boundary.

Routes are enumerated from the composed application rather than listed by hand,
so a newly added route is automatically checked and must be classified.
"""
import re
import uuid

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from autograder.models.capabilities import HostCapabilities
from tests.web.test_contracts_v1 import definition, external
from web.core.config import Settings, parse_attestation_tokens

TOKEN = "int01-integration-token"
PRODUCER_TOKEN = "int01-actions-producer-token"
OTHER_PRODUCER_TOKEN = "int01-other-producer-token"

PUBLIC = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/ready"),
    ("GET", "/api/v1/templates"),
    ("GET", "/api/v1/templates/{template_name}"),
}
ATTESTATION = {("POST", "/api/v1/submissions/external-results")}


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _app(session_factory, tmp_path, **settings):
    from web.main import create_app

    values = {"INTEGRATION_TOKEN": TOKEN,
              "ATTESTATION_TOKENS": {"actions": PRODUCER_TOKEN, "other": OTHER_PRODUCER_TOKEN},
              "RECEIPT_DIR": str(tmp_path / "receipts")} | settings
    app = create_app(Settings(**values), session_factory=session_factory,
                     capabilities=HostCapabilities(), start_workers=False)
    app.state.host.ready = True
    return app


@pytest.fixture
async def secured(session_factory, tmp_path):
    app = _app(session_factory, tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield app, client
    await app.state.host.close()


def _routes():
    from web.main import create_app

    app = create_app(Settings(INTEGRATION_TOKEN=TOKEN, DATABASE_URL="sqlite+aiosqlite://"),
                     session_factory=lambda: None, capabilities=HostCapabilities(), start_workers=False)
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods):
                yield method, route.path


ALL_ROUTES = sorted(set(_routes()))
PROTECTED = [route for route in ALL_ROUTES if route not in PUBLIC]


def _concrete(path):
    return re.sub(r"\{[^}]+\}", "1", path)


async def _call(client, method, path, headers):
    kwargs = {"headers": headers}
    if method in ("POST", "PATCH", "PUT"):
        kwargs["json"] = {}
    return await client.request(method, _concrete(path), **kwargs)


def test_every_route_is_classified():
    """A new route cannot silently join the public set."""
    assert set(PUBLIC) <= set(ALL_ROUTES)
    assert set(ATTESTATION) <= set(PROTECTED)
    # Spot check the aliases named by the original INT-01 finding.
    for alias in [("GET", "/api/v1/configs/id/{config_id}"),
                  ("GET", "/api/v1/configs/{external_assignment_id}"),
                  ("PATCH", "/api/v1/configs/external/{external_assignment_id}"),
                  ("PATCH", "/api/v1/configs/{config_id}"),
                  ("POST", "/api/v1/configs"),
                  ("POST", "/api/v1/configs/validate"),
                  ("POST", "/api/v1/submissions"),
                  ("GET", "/api/v1/submissions/{submission_id}"),
                  ("GET", "/api/v1/submissions/user/{external_user_id}"),
                  ("POST", "/api/v1/execute")]:
        assert alias in PROTECTED


@pytest.mark.parametrize("method,path", PROTECTED)
@pytest.mark.parametrize("headers,detail", [
    ({}, "missing"),
    ({"Authorization": ""}, "missing"),
    ({"Authorization": f"Basic {TOKEN}"}, "missing"),
    (_bearer("wrong-token"), "invalid"),
    (_bearer(TOKEN + "x"), "invalid"),
    (_bearer(TOKEN[:-1]), "invalid"),
], ids=["absent", "empty", "basic-scheme", "wrong", "suffix", "prefix"])
async def test_protected_routes_reject_missing_and_bad_tokens(secured, method, path, headers, detail):
    _, client = secured
    response = await _call(client, method, path, headers)
    assert response.status_code == 401, (method, path, response.text)
    assert detail in response.json()["detail"].lower()
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_valid_integration_token_passes_the_boundary(secured, method, path):
    _, client = secured
    response = await _call(client, method, path, _bearer(TOKEN))
    assert response.status_code not in (401, 403, 503), (method, path, response.text)


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_restricted_producer_may_only_attest(secured, method, path):
    _, client = secured
    response = await _call(client, method, path, _bearer(PRODUCER_TOKEN))
    if (method, path) in ATTESTATION:
        assert response.status_code == 422  # authenticated; empty body is invalid
    else:
        assert response.status_code == 403, (method, path, response.text)


@pytest.mark.parametrize("method,path", sorted(PUBLIC))
async def test_public_routes_need_no_credentials(secured, method, path):
    _, client = secured
    response = await _call(client, method, path.replace("{template_name}", "input_output"), {})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_unconfigured_host_fails_closed(session_factory, tmp_path, method, path):
    app = _app(session_factory, tmp_path, INTEGRATION_TOKEN="", ATTESTATION_TOKENS={})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _call(client, method, path, _bearer("anything"))
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
    await app.state.host.close()


async def test_no_alias_bypasses_configuration_protection(secured):
    _, client = secured
    alias = f"alias-{uuid.uuid4().hex[:8]}"
    created = await client.post("/api/v1/configs", headers=_bearer(TOKEN),
                                json={"external_assignment_id": alias, "definition": definition()})
    assert created.status_code == 200
    config_id = created.json()["id"]
    for path in (f"/api/v1/configs/id/{config_id}", f"/api/v1/configs/{alias}", "/api/v1/configs"):
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers=_bearer(PRODUCER_TOKEN))).status_code == 403
        assert (await client.get(path, headers=_bearer(TOKEN))).status_code == 200
    for path in (f"/api/v1/configs/{config_id}", f"/api/v1/configs/external/{alias}"):
        response = await client.patch(path, headers={"If-Match": '"1"'}, json={"is_active": False})
        assert response.status_code == 401
    # Nothing was changed by the rejected requests.
    assert (await client.get(f"/api/v1/configs/{alias}", headers=_bearer(TOKEN))).json()["version"] == 1


async def test_submitted_code_is_not_readable_without_integration_scope(secured):
    _, client = secured
    alias = f"code-{uuid.uuid4().hex[:8]}"
    await client.post("/api/v1/configs", headers=_bearer(TOKEN),
                      json={"external_assignment_id": alias, "definition": definition()})
    accepted = await client.post("/api/v1/submissions", headers=_bearer(TOKEN), json={
        "external_assignment_id": alias, "external_user_id": "student", "username": "student",
        "files": [{"filename": "main.py", "content": "SECRET_SOURCE = 1"}]})
    assert accepted.status_code == 202
    submission = accepted.json()["id"]
    for path in (f"/api/v1/submissions/{submission}", f"/api/v1/submissions/{submission}/details",
                 "/api/v1/submissions", "/api/v1/submissions/user/student"):
        for headers in ({}, _bearer(PRODUCER_TOKEN)):
            response = await client.get(path, headers=headers)
            assert response.status_code in (401, 403)
            assert "SECRET_SOURCE" not in response.text
    details = await client.get(f"/api/v1/submissions/{submission}/details", headers=_bearer(TOKEN))
    assert "SECRET_SOURCE" in details.text


async def test_restricted_producer_attests_and_receives_only_its_receipt(secured):
    _, client = secured
    created = await client.post("/api/v1/configs", headers=_bearer(TOKEN), json={
        "external_assignment_id": f"attest-{uuid.uuid4().hex[:8]}", "definition": definition()})
    payload = external(created.json(), score=100)
    response = await client.post("/api/v1/submissions/external-results", json=payload,
                                 headers=_bearer(PRODUCER_TOKEN))
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert set(receipt) >= {"submission_id", "final_score", "provenance"}
    assert "submission_files" not in receipt and "definition_snapshot" not in receipt
    # The producer cannot read the record back through ordinary submission routes.
    assert (await client.get(f"/api/v1/submissions/{receipt['submission_id']}",
                             headers=_bearer(PRODUCER_TOKEN))).status_code == 403


async def test_lowercase_bearer_scheme_is_accepted(secured):
    _, client = secured
    response = await client.get("/api/v1/configs", headers={"Authorization": f"bearer {TOKEN}"})
    assert response.status_code == 200


async def test_readiness_reports_missing_authentication(session_factory, tmp_path):
    app = _app(session_factory, tmp_path, INTEGRATION_TOKEN="", ATTESTATION_TOKENS={})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json()["authentication"] == "not_configured"
        assert response.json()["ready"] is False
    await app.state.host.close()


async def test_readiness_reports_configured_authentication(secured):
    _, client = secured
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["authentication"] == "configured"


async def test_startup_logs_missing_authentication(session_factory, tmp_path, monkeypatch):
    from web.core import host as host_module

    messages = []
    monkeypatch.setattr(host_module.logger, "error", lambda message, *args, **kwargs: messages.append(message))
    app = _app(session_factory, tmp_path, INTEGRATION_TOKEN="", ATTESTATION_TOKENS={})
    await app.state.host.start()
    try:
        assert any("authentication_not_configured" in message for message in messages)
    finally:
        await app.state.host.close()


def test_openapi_declares_auth_accurately():
    from web.main import create_app

    schema = create_app(Settings(INTEGRATION_TOKEN=TOKEN), session_factory=lambda: None,
                        capabilities=HostCapabilities(), start_workers=False).openapi()
    assert schema["components"]["securitySchemes"]["IntegrationBearer"]["scheme"] == "bearer"
    for method, path in ALL_ROUTES:
        operation = schema["paths"][path][method.lower()]
        if (method, path) in PUBLIC:
            assert "security" not in operation, (method, path)
        else:
            assert operation["security"] == [{"IntegrationBearer": []}], (method, path)
            assert {"401", "403", "503"} <= set(operation["responses"]), (method, path)


def test_attestation_token_parsing_and_validation():
    assert parse_attestation_tokens("") == {}
    assert parse_attestation_tokens(" actions = a-token , prisma=p-token ,") == {
        "actions": "a-token", "prisma": "p-token"}
    for invalid in ("actions", "actions=", "a=x,a=y"):
        with pytest.raises(ValueError):
            parse_attestation_tokens(invalid)
    with pytest.raises(ValueError, match="distinct"):
        Settings(INTEGRATION_TOKEN="same", ATTESTATION_TOKENS={"actions": "same"})
    with pytest.raises(ValueError, match="distinct"):
        Settings(ATTESTATION_TOKENS={"a": "same", "b": "same"})
    with pytest.raises(ValueError, match="producer name"):
        Settings(ATTESTATION_TOKENS={"Bad Name": "x"})


def test_attestation_tokens_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_ATTESTATION_TOKENS", "actions=env-token")
    assert Settings(INTEGRATION_TOKEN="other").ATTESTATION_TOKENS == {"actions": "env-token"}
