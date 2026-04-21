"""Tests for config fetch by ID and external result ingestion endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

import web.config.auth as auth_module
from web.config.auth import IntegrationAuthConfig
from web.database.base import Base
from web.database import session

TEST_TOKEN = "test-external-results-token"

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
    cfg = IntegrationAuthConfig.__new__(IntegrationAuthConfig)
    cfg.token = TEST_TOKEN
    auth_module.integration_auth_config = cfg
    yield
    auth_module.integration_auth_config = cfg

def _auth_header() -> dict:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}

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

async def _create_config(client, external_id="ext-assign-1"):
    """Helper to create a grading config and return its internal ID."""
    config_data = {
        "external_assignment_id": external_id,
        "template_name": "input_output",
        "languages": ["python"],
        "criteria_config": {"base": {"tests": ["test_hello"]}},
        "setup_config": {"main_file": "main.py"},
        "feedback_config": {"show_score": True},
        "include_feedback": True,
    }
    resp = await client.post("/api/v1/configs", json=config_data)
    assert resp.status_code == 200
    return resp.json()

# ---------------------------------------------------------------------------
# GET /api/v1/configs/id/{config_id}
# ---------------------------------------------------------------------------

class TestGetConfigById:
    """Tests for fetching grading config by internal ID."""

    @pytest.mark.asyncio
    async def test_get_config_by_id_success(self, client):
        """Fetch an existing config by its internal ID."""
        created = await _create_config(client, "id-lookup-1")
        config_id = created["id"]

        response = await client.get(f"/api/v1/configs/id/{config_id}", headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == config_id
        assert data["external_assignment_id"] == "id-lookup-1"
        assert data["template_name"] == "input_output"
        assert data["languages"] == ["python"]
        assert data["criteria_config"] == {"base": {"tests": ["test_hello"]}}
        assert data["setup_config"] == {"main_file": "main.py"}
        assert data["feedback_config"] == {"show_score": True}
        assert data["include_feedback"] is True
        assert data["version"] is not None
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_config_by_id_not_found(self, client):
        """Return 404 for non-existent config ID."""
        response = await client.get("/api/v1/configs/id/99999", headers=_auth_header())
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_config_by_id_returns_all_fields(self, client):
        """Response includes all fields required by build_pipeline."""
        created = await _create_config(client, "id-lookup-fields")
        config_id = created["id"]

        response = await client.get(f"/api/v1/configs/id/{config_id}", headers=_auth_header())
        data = response.json()

        required_keys = [
            "template_name", "criteria_config", "setup_config",
            "feedback_config", "include_feedback", "languages",
            "external_assignment_id", "version", "is_active",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

# ---------------------------------------------------------------------------
# POST /api/v1/submissions/external-results
# ---------------------------------------------------------------------------

class TestExternalResultIngestion:
    """Tests for external grading result ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_completed_result(self, client):
        """Successfully ingest a completed external result."""
        created = await _create_config(client, "ext-result-1")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-42",
            "username": "alice",
            "language": "python",
            "status": "completed",
            "final_score": 85.5,
            "feedback": "Good job!",
            "result_tree": {"root": {"score": 85.5}},
            "focus": {"failed": []},
            "pipeline_execution": {"steps": ["grade"]},
            "execution_time_ms": 1234,
            "submission_metadata": {"repo": "org/repo", "run_id": "123"},
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["submission_id"] is not None
        assert data["grading_config_id"] == config_id
        assert data["external_user_id"] == "student-42"
        assert data["username"] == "alice"
        assert data["status"] == "completed"
        assert data["final_score"] == 85.5
        assert data["graded_at"] is not None
        assert data["execution_time_ms"] == 1234

    @pytest.mark.asyncio
    async def test_ingest_failed_result(self, client):
        """Successfully ingest a failed external result."""
        created = await _create_config(client, "ext-result-fail")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-43",
            "username": "bob",
            "language": "python",
            "status": "failed",
            "final_score": 0.0,
            "execution_time_ms": 500,
            "error_message": "Compilation error",
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["final_score"] == 0.0

    @pytest.mark.asyncio
    async def test_ingest_result_visible_via_submission_detail(self, client):
        """Ingested result is visible through the existing submission detail endpoint."""
        created = await _create_config(client, "ext-result-visible")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-44",
            "username": "carol",
            "language": "python",
            "status": "completed",
            "final_score": 92.0,
            "feedback": "Excellent",
            "result_tree": {"root": {"score": 92.0}},
            "focus": {"top": "test_1"},
            "execution_time_ms": 800,
        }

        ingest_resp = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert ingest_resp.status_code == 200
        submission_id = ingest_resp.json()["submission_id"]

        # Retrieve via existing detail endpoint
        detail_resp = await client.get(f"/api/v1/submissions/{submission_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["final_score"] == 92.0
        assert detail["feedback"] == "Excellent"
        assert detail["result_tree"] == {"root": {"score": 92.0}}
        assert detail["focus"] == {"top": "test_1"}
        assert detail["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ingest_result_visible_via_user_submissions(self, client):
        """Ingested result is visible through the user submissions list endpoint."""
        created = await _create_config(client, "ext-result-user")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-unique-45",
            "username": "dave",
            "language": "python",
            "status": "completed",
            "final_score": 77.0,
            "execution_time_ms": 600,
        }

        await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())

        user_resp = await client.get("/api/v1/submissions/user/student-unique-45")
        assert user_resp.status_code == 200
        submissions = user_resp.json()
        assert len(submissions) >= 1
        assert submissions[0]["external_user_id"] == "student-unique-45"
        assert submissions[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ingest_result_config_not_found(self, client):
        """Return 404 when grading config does not exist."""
        payload = {
            "grading_config_id": 99999,
            "external_user_id": "student-50",
            "username": "eve",
            "language": "python",
            "status": "completed",
            "final_score": 50.0,
            "execution_time_ms": 100,
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_ingest_result_unsupported_language(self, client):
        """Return 400 when language is not supported by the config."""
        created = await _create_config(client, "ext-result-badlang")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-51",
            "username": "frank",
            "language": "java",  # config only supports python
            "status": "completed",
            "final_score": 50.0,
            "execution_time_ms": 100,
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_ingest_result_invalid_language(self, client):
        """Return 422 for a completely invalid language value."""
        created = await _create_config(client, "ext-result-invalidlang")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-52",
            "username": "grace",
            "language": "brainfuck",
            "status": "completed",
            "final_score": 50.0,
            "execution_time_ms": 100,
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_ingest_result_invalid_status(self, client):
        """Return 422 for an invalid status value."""
        created = await _create_config(client, "ext-result-badstatus")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-53",
            "username": "heidi",
            "language": "python",
            "status": "pending",  # not valid for external results
            "final_score": 50.0,
            "execution_time_ms": 100,
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_result_negative_score(self, client):
        """Return 422 for a negative final score."""
        created = await _create_config(client, "ext-result-negscore")
        config_id = created["id"]

        payload = {
            "grading_config_id": config_id,
            "external_user_id": "student-54",
            "username": "ivan",
            "language": "python",
            "status": "completed",
            "final_score": -10.0,
            "execution_time_ms": 100,
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_result_missing_required_fields(self, client):
        """Return 422 when required fields are missing."""
        payload = {
            "grading_config_id": 1,
            "external_user_id": "student-55",
            # missing username, language, status, final_score, execution_time_ms
        }

        response = await client.post("/api/v1/submissions/external-results", json=payload, headers=_auth_header())
        assert response.status_code == 422
