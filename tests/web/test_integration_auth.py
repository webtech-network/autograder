from tests.web.test_contracts_v1 import definition

"""Tests for M2M integration token authentication on protected endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from web.database.base import Base

TEST_TOKEN = "test-integration-secret-token-abc123"


@pytest.fixture(autouse=True)
def _set_integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", TEST_TOKEN)


def _auth_header(token: str = TEST_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_config(client):
    """Helper — config creation is public, no auth needed."""
    import uuid

    config_data = {
        "external_assignment_id": f"auth-test-{uuid.uuid4().hex[:8]}",
        "definition": definition(),
    }
    resp = await client.post("/api/v1/configs", json=config_data)
    assert resp.status_code == 200
    return resp.json()


class TestAuthMissingToken:
    """Requests without a token get 401."""

    @pytest.mark.asyncio
    async def test_config_by_id_no_token_401(self, client):
        resp = await client.get("/api/v1/configs/id/1")
        assert resp.status_code == 401
        assert "missing" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_external_results_no_token_401(self, client):
        payload = {
            "grading_config_id": 1,
            "external_user_id": "u1",
            "username": "student",
            "language": "python",
            "status": "completed",
            "final_score": 100.0,
            "execution_time_ms": 100,
        }
        resp = await client.post("/api/v1/submissions/external-results", json=payload)
        assert resp.status_code == 401


class TestAuthInvalidToken:
    """Requests with a wrong token get 401."""

    @pytest.mark.asyncio
    async def test_config_by_id_wrong_token_401(self, client):
        resp = await client.get(
            "/api/v1/configs/id/1", headers=_auth_header("wrong-token")
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_external_results_wrong_token_401(self, client):
        payload = {
            "grading_config_id": 1,
            "external_user_id": "u1",
            "username": "student",
            "language": "python",
            "status": "completed",
            "final_score": 100.0,
            "execution_time_ms": 100,
        }
        resp = await client.post(
            "/api/v1/submissions/external-results",
            json=payload,
            headers=_auth_header("wrong-token"),
        )
        assert resp.status_code == 401


class TestAuthValidToken:
    """Valid token grants access to protected endpoints."""

    @pytest.mark.asyncio
    async def test_config_by_id_valid_token(self, client):
        created = await _create_config(client)
        resp = await client.get(
            f"/api/v1/configs/id/{created['id']}", headers=_auth_header()
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    @pytest.mark.asyncio
    async def test_external_results_valid_token(self, client):
        created = await _create_config(client)
        from tests.web.test_contracts_v1 import external

        payload = external(created, score=100)
        resp = await client.post(
            "/api/v1/submissions/external-results", json=payload, headers=_auth_header()
        )
        assert resp.status_code == 200
        assert resp.json()["final_score"] == 100.0

    @pytest.mark.asyncio
    async def test_config_by_id_not_found_still_404(self, client):
        """Auth passes but resource doesn't exist → 404, not 401."""
        resp = await client.get("/api/v1/configs/id/99999", headers=_auth_header())
        assert resp.status_code == 404


class TestPublicEndpointsUnaffected:
    """Token auth must not affect public endpoints."""

    @pytest.mark.asyncio
    async def test_create_config_no_auth(self, client):
        resp = await client.post(
            "/api/v1/configs",
            json={
                "external_assignment_id": "public-test-cfg",
                "definition": definition(),
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_config_by_external_id_no_auth(self, client):
        await client.post(
            "/api/v1/configs",
            json={
                "external_assignment_id": "public-ext-id",
                "definition": definition(),
            },
        )
        resp = await client.get("/api/v1/configs/public-ext-id")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_configs_no_auth(self, client):
        resp = await client.get("/api/v1/configs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_no_auth(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_submission_no_auth(self, client):
        resp = await client.get("/api/v1/submissions/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_user_submissions_no_auth(self, client):
        resp = await client.get("/api/v1/submissions/user/nobody")
        assert resp.status_code == 200
