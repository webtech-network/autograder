"""Integration tests for the refactored API routes structure.

Tests verify that the new route organization works correctly with proper
endpoints, HTTP methods, and response formats.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from web.database.base import Base
from web.database import session


# Mock external dependencies before importing
@pytest.fixture(scope="module", autouse=True)
def mock_external_services():
    """Mock external services for all tests."""
    with patch("web.core.lifespan.initialize_sandbox_manager"), \
         patch("web.core.lifespan.TemplateLibraryService") as mock_template, \
         patch("web.core.lifespan.SandboxPoolConfig.load_from_yaml", return_value=[]):

        # Setup template service mock
        mock_service = Mock()
        mock_service.get_all_templates_info = Mock(return_value=[
            {"name": "webdev", "description": "Web development grading"},
            {"name": "input_output", "description": "Input/output testing"}
        ])
        mock_service.get_template_info = Mock(return_value={
            "name": "webdev",
            "description": "Web development grading",
            "supported_languages": ["python", "javascript"]
        })
        mock_template.get_instance.return_value = mock_service

        yield


# Import app after mocking
from web.main import app


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
    session.AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session.engine = engine

    yield engine

    session.AsyncSessionLocal = old_session_maker
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test /api/v1/health endpoint."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, client):
        """Test /api/v1/ready endpoint."""
        response = await client.get("/api/v1/ready")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data
        assert "timestamp" in data


class TestTemplateEndpoints:
    """Test template-related endpoints."""

    @pytest.mark.asyncio
    async def test_list_templates(self, client):
        """Test GET /api/v1/templates."""
        with patch("web.core.lifespan.get_template_service") as mock_get:
            mock_service = Mock()
            mock_service.get_all_templates_info = Mock(return_value=[
                {"name": "webdev", "description": "Web dev"},
                {"name": "api_testing", "description": "API testing"}
            ])
            mock_get.return_value = mock_service

            response = await client.get("/api/v1/templates")
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data
            assert len(data["templates"]) == 2

    @pytest.mark.asyncio
    async def test_get_template_info(self, client):
        """Test GET /api/v1/templates/{name}."""
        with patch("web.core.lifespan.get_template_service") as mock_get:
            mock_service = Mock()
            mock_service.get_template_info = Mock(return_value={
                "name": "webdev",
                "description": "Web development",
                "supported_languages": ["python", "javascript"]
            })
            mock_get.return_value = mock_service

            response = await client.get("/api/v1/templates/webdev")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "webdev"
            assert "supported_languages" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, client):
        """Test GET /api/v1/templates/{name} with invalid template."""
        with patch("web.core.lifespan.get_template_service") as mock_get:
            mock_service = Mock()
            mock_service.get_template_info = Mock(side_effect=KeyError("Template not found"))
            mock_get.return_value = mock_service

            response = await client.get("/api/v1/templates/nonexistent")
            assert response.status_code == 404


class TestGradingConfigEndpoints:
    """Test grading configuration endpoints."""

    @pytest.mark.asyncio
    async def test_create_config(self, client):
        """Test POST /api/v1/configs."""
        config_data = {
            "external_assignment_id": "assign-001",
            "template_name": "webdev",
            "languages": ["python"],
            "criteria_config": {
                "base": {"tests": ["test_homepage"]}
            }
        }

        response = await client.post("/api/v1/configs", json=config_data)
        assert response.status_code == 200
        data = response.json()
        assert data["external_assignment_id"] == "assign-001"
        assert data["template_name"] == "webdev"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_config(self, client):
        """Test creating duplicate config returns 400."""
        config_data = {
            "external_assignment_id": "assign-002",
            "template_name": "webdev",
            "languages": ["python"],
            "criteria_config": {"base": {}}
        }

        # Create first config
        response1 = await client.post("/api/v1/configs", json=config_data)
        assert response1.status_code == 200

        # Try to create duplicate
        response2 = await client.post("/api/v1/configs", json=config_data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_config_by_external_id(self, client):
        """Test GET /api/v1/configs/{external_assignment_id}."""
        # First create a config
        config_data = {
            "external_assignment_id": "assign-003",
            "template_name": "input_output",
            "languages": ["java"],
            "criteria_config": {"base": {}}
        }
        await client.post("/api/v1/configs", json=config_data)

        # Get it back
        response = await client.get("/api/v1/configs/assign-003")
        assert response.status_code == 200
        data = response.json()
        assert data["external_assignment_id"] == "assign-003"
        assert data["template_name"] == "input_output"

    @pytest.mark.asyncio
    async def test_get_nonexistent_config(self, client):
        """Test GET /api/v1/configs/{external_assignment_id} returns 404."""
        response = await client.get("/api/v1/configs/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_configs(self, client):
        """Test GET /api/v1/configs."""
        # Create multiple configs
        for i in range(3):
            config_data = {
                "external_assignment_id": f"list-test-{i}",
                "template_name": "webdev",
                "languages": ["python"],
                "criteria_config": {}
            }
            await client.post("/api/v1/configs", json=config_data)

        response = await client.get("/api/v1/configs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    @pytest.mark.asyncio
    async def test_update_config(self, client):
        """Test PUT /api/v1/configs/{id}."""
        # Create config
        config_data = {
            "external_assignment_id": "assign-update",
            "template_name": "webdev",
            "languages": ["python"],
            "criteria_config": {"base": {}}
        }
        create_response = await client.post("/api/v1/configs", json=config_data)
        config_id = create_response.json()["id"]

        # Update it
        update_data = {
            "criteria_config": {"base": {"updated": True}}
        }
        response = await client.put(f"/api/v1/configs/{config_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["criteria_config"]["base"]["updated"] is True


class TestSubmissionEndpoints:
    """Test submission endpoints."""

    @pytest.mark.asyncio
    async def test_create_submission(self, client):
        """Test POST /api/v1/submissions."""
        # First create a config
        config_data = {
            "external_assignment_id": "submit-test-1",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {"base": {}}
        }
        await client.post("/api/v1/configs", json=config_data)

        # Mock the grading task
        with patch("web.api.v1.submissions.asyncio.create_task") as mock_task, \
             patch("web.api.v1.submissions.grade_submission", new_callable=AsyncMock):

            mock_task.return_value = Mock(add_done_callback=Mock())

            # Create submission
            submission_data = {
                "external_assignment_id": "submit-test-1",
                "external_user_id": "user_001",
                "username": "student1",
                "files": [
                    {"filename": "main.py", "content": "print('hello')"}
                ]
            }

            response = await client.post("/api/v1/submissions", json=submission_data)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] is not None
            assert data["username"] == "student1"
            assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_submission_with_language(self, client):
        """Test creating submission with explicit language."""
        config_data = {
            "external_assignment_id": "submit-lang-test",
            "template_name": "input_output",
            "languages": ["python", "java"],
            "criteria_config": {}
        }
        await client.post("/api/v1/configs", json=config_data)

        with patch("web.api.v1.submissions.asyncio.create_task") as mock_task, \
             patch("web.api.v1.submissions.grade_submission", new_callable=AsyncMock):

            mock_task.return_value = Mock(add_done_callback=Mock())

            submission_data = {
                "external_assignment_id": "submit-lang-test",
                "external_user_id": "user_002",
                "username": "student2",
                "language": "java",
                "files": [
                    {"filename": "Main.java", "content": "public class Main {}"}
                ]
            }

            response = await client.post("/api/v1/submissions", json=submission_data)
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "java"

    @pytest.mark.asyncio
    async def test_create_submission_invalid_language(self, client):
        """Test creating submission with unsupported language."""
        config_data = {
            "external_assignment_id": "submit-invalid-lang",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {}
        }
        await client.post("/api/v1/configs", json=config_data)

        submission_data = {
            "external_assignment_id": "submit-invalid-lang",
            "external_user_id": "user_003",
            "username": "student3",
            "language": "ruby",  # Not supported
            "files": [{"filename": "main.rb", "content": "puts 'hello'"}]
        }

        response = await client.post("/api/v1/submissions", json=submission_data)
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_submission(self, client):
        """Test GET /api/v1/submissions/{id}."""
        # Create config and submission
        config_data = {
            "external_assignment_id": "get-submit-test",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {}
        }
        await client.post("/api/v1/configs", json=config_data)

        with patch("web.api.v1.submissions.asyncio.create_task") as mock_task, \
             patch("web.api.v1.submissions.grade_submission", new_callable=AsyncMock):

            mock_task.return_value = Mock(add_done_callback=Mock())

            submission_data = {
                "external_assignment_id": "get-submit-test",
                "external_user_id": "user_004",
                "username": "student4",
                "files": [{"filename": "main.py", "content": "print('test')"}]
            }

            create_response = await client.post("/api/v1/submissions", json=submission_data)
            submission_id = create_response.json()["id"]

            # Get submission
            response = await client.get(f"/api/v1/submissions/{submission_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == submission_id
            assert data["username"] == "student4"
            assert "submission_files" in data

    @pytest.mark.asyncio
    async def test_get_user_submissions(self, client):
        """Test GET /api/v1/submissions/user/{external_user_id}."""
        # Create config
        config_data = {
            "external_assignment_id": "user-submits-test",
            "template_name": "input_output",
            "languages": ["python"],
            "criteria_config": {}
        }
        await client.post("/api/v1/configs", json=config_data)

        with patch("web.api.v1.submissions.asyncio.create_task") as mock_task, \
             patch("web.api.v1.submissions.grade_submission", new_callable=AsyncMock):

            mock_task.return_value = Mock(add_done_callback=Mock())

            # Create multiple submissions for same user
            for i in range(3):
                submission_data = {
                    "external_assignment_id": "user-submits-test",
                    "external_user_id": "user_multi",
                    "username": "student_multi",
                    "files": [{"filename": "main.py", "content": f"print({i})"}]
                }
                await client.post("/api/v1/submissions", json=submission_data)

            # Get all submissions for user
            response = await client.get("/api/v1/submissions/user/user_multi")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 3
            assert all(s["external_user_id"] == "user_multi" for s in data)

