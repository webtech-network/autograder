"""Tests for M2M integration token authentication on protected endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

import web.config.auth as auth_module
from web.config.auth import IntegrationAuthConfig
from web.database.base import Base
from web.database import session

TEST_TOKEN = "test-integration-secret-token-abc123"

@pytest.fixture(scope="module", autouse=True)
def mock_external_services():
    """Mock external services for all tests."""
    with patch("web.core.lifespan.initialize_sandbox_manager"), \
         patch("web.core.lifespan.TemplateLibraryService") as mock_template, \
         patch("web.core.lifespan.SandboxPoolConfig.load_from_yaml", return_value=[]):

        mock_service = Mock()
        mock_service.get_all_templates_info = Mock(return_value=[
            {"name": "input_output", "description": "I/O testing"}
        ])
        mock_service.get_template_info = Mock(return_value={
            "name": "input_output",
            "description": "I/O testing",
            "supported_languages": ["python"],
        })
        mock_template.get_instance.return_value = mock_service
        yield

from web.main import app

@pytest.fixture(autouse=True)
def _set_integration_token():
    """Ensure the integration token is set for every test."""
    old_integration_auth_config = getattr(auth_module, "integration_auth_config", None)
    cfg = IntegrationAuthConfig.__new__(IntegrationAuthConfig)
    cfg.token = TEST_TOKEN
    auth_module.integration_auth_config = cfg
    yield
    auth_module.integration_auth_config = old_integration_auth_config

@pytest.fixture
async def test_db():
    """Create a fresh test database for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    old_session_maker = session.AsyncSessionLocal
    old_engine = getattr(session, "engine", None)
    session.AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session.engine = engine

    yield engine

    session.AsyncSessionLocal = old_session_maker
    if old_engine is not None:
        session.engine = old_engine
    await engine.dispose()

@pytest.fixture
async def client(test_db):
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

def _auth_header(token: str = TEST_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}

async def _create_config(client):
    """Helper — config creation is public, no auth needed."""
    import uuid
    config_data = {
        "external_assignment_id": f"auth-test-{uuid.uuid4().hex[:8]}",
        "template_name": "input_output",
        "languages": ["python"],
        "criteria_config": {"base": {"tests": ["test_hello"]}},
    }
    resp = await client.post("/api/v1/configs", json=config_data)
    assert resp.status_code == 200
    return resp.json()

# ---------------------------------------------------------------------------
# Missing token → 401
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Wrong token → 401
# ---------------------------------------------------------------------------

class TestAuthInvalidToken:
    """Requests with a wrong token get 401."""

    @pytest.mark.asyncio
    async def test_config_by_id_wrong_token_401(self, client):
        resp = await client.get(
            "/api/v1/configs/id/1",
            headers=_auth_header("wrong-token"),
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

# ---------------------------------------------------------------------------
# Valid token → success
# ---------------------------------------------------------------------------

class TestAuthValidToken:
    """Valid token grants access to protected endpoints."""

    @pytest.mark.asyncio
    async def test_config_by_id_valid_token(self, client):
        created = await _create_config(client)
        resp = await client.get(
            f"/api/v1/configs/id/{created['id']}",
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    @pytest.mark.asyncio
    async def test_external_results_valid_token(self, client):
        created = await _create_config(client)
        payload = {
            "grading_config_id": created["id"],
            "external_user_id": "u-auth",
            "username": "student_auth",
            "language": "python",
            "status": "completed",
            "final_score": 95.0,
            "execution_time_ms": 200,
        }
        resp = await client.post(
            "/api/v1/submissions/external-results",
            json=payload,
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["final_score"] == 95.0

    @pytest.mark.asyncio
    async def test_config_by_id_not_found_still_404(self, client):
        """Auth passes but resource doesn't exist → 404, not 401."""
        resp = await client.get(
            "/api/v1/configs/id/99999",
            headers=_auth_header(),
        )
        assert resp.status_code == 404

# ---------------------------------------------------------------------------
# Public endpoints stay public
# ---------------------------------------------------------------------------

class TestPublicEndpointsUnaffected:
    """Token auth must not affect public endpoints."""

    @pytest.mark.asyncio
    async def test_create_config_no_auth(self, client):
        resp = await client.post("/api/v1/configs", json={
            "external_assignment_id": "public-test-cfg",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {},
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_config_by_external_id_no_auth(self, client):
        await client.post("/api/v1/configs", json={
            "external_assignment_id": "public-ext-id",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {},
        })
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
        assert resp.status_code == 404  # not 401

    @pytest.mark.asyncio
    async def test_list_user_submissions_no_auth(self, client):
        resp = await client.get("/api/v1/submissions/user/nobody")
        assert resp.status_code == 200
