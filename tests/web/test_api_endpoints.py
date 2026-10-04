from tests.web.test_contracts_v1 import definition

"""Integration tests for the API endpoints.

These tests verify the API functionality without requiring Docker/sandboxes.
They use mocked sandbox manager and template library.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from web.database.base import Base
from web.database import session
from web.schemas.execution import (
    DeliberateCodeExecutionResponse,
    DeliberateCodeExecutionResult,
)
from sandbox_manager.models.sandbox_models import ResponseCategory


@pytest.fixture(scope="module", autouse=True)
def mock_external_services():
    """Mock external services for all tests."""
    with patch("web.core.lifespan.initialize_sandbox_manager"), patch(
        "web.core.lifespan.TemplateLibraryService"
    ) as mock_template, patch(
        "web.core.lifespan.SandboxPoolConfig.load_from_yaml", return_value=[]
    ):
        mock_service = Mock()
        mock_service.get_all_templates_info = Mock(
            return_value=[
                {"name": "webdev", "description": "Web development grading"},
                {"name": "api", "description": "API testing"},
            ]
        )
        mock_service.get_template_info = Mock(
            return_value={
                "name": "webdev",
                "description": "Web development grading",
                "supported_languages": ["python", "javascript"],
            }
        )
        mock_template.get_instance.return_value = mock_service
        yield


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
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = await client.get("/api/v1/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "ready" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_execute_endpoint_contract_and_value_error_mapping(client):
    """Test /api/v1/execute response contract and ValueError mapping."""
    execute_request = {
        "language": "python",
        "submission_files": [{"filename": "main.py", "content": "print('ok')"}],
        "program_command": "python main.py",
    }
    service_response = DeliberateCodeExecutionResponse(
        results=[
            DeliberateCodeExecutionResult(
                output="ok\n",
                category=ResponseCategory.SUCCESS,
                error_message=None,
                execution_time=0.12,
            )
        ]
    )
    with patch(
        "web.api.v1.execution.execute_code",
        new=AsyncMock(return_value=service_response),
    ):
        response = await client.post("/api/v1/execute", json=execute_request)
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert set(result.keys()) == {
        "output",
        "category",
        "error_message",
        "execution_time",
    }
    assert result["output"] == "ok\n"
    assert result["category"] == "success"
    assert result["error_message"] is None
    assert isinstance(result["execution_time"], float)
    with patch(
        "web.api.v1.execution.execute_code",
        new=AsyncMock(side_effect=ValueError("invalid request")),
    ):
        error_response = await client.post("/api/v1/execute", json=execute_request)
    assert error_response.status_code == 400
    assert error_response.json()["detail"] == "invalid request"


@pytest.mark.asyncio
async def test_create_grading_config(client):
    """Test creating a grading configuration."""
    config_data = {
        "external_assignment_id": "test-assignment-1",
        "definition": definition(),
    }
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 200
    data = response.json()
    assert data["external_assignment_id"] == "test-assignment-1"
    assert data["definition"]["templates"] == ["input_output"]
    assert data["definition"]["languages"] == ["python"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_grading_config(client):
    """Test retrieving a grading configuration."""
    config_data = {
        "external_assignment_id": "test-assignment-2",
        "definition": definition(),
    }
    await client.post("/api/v1/configs", json=config_data)
    response = await client.get("/api/v1/configs/test-assignment-2")
    assert response.status_code == 200
    data = response.json()
    assert data["external_assignment_id"] == "test-assignment-2"
    assert data["definition"]["templates"] == ["input_output"]


@pytest.mark.asyncio
async def test_list_grading_configs(client):
    """Test listing grading configurations."""
    for i in range(3):
        config_data = {
            "external_assignment_id": f"test-assignment-list-{i}",
            "definition": definition(),
        }
        await client.post("/api/v1/configs", json=config_data)
    response = await client.get("/api/v1/configs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


@pytest.mark.asyncio
async def test_create_submission_without_config(client):
    """Test creating a submission without a config fails."""
    submission_data = {
        "external_assignment_id": "nonexistent-assignment",
        "external_user_id": "user-123",
        "username": "testuser",
        "files": [{"filename": "main.py", "content": "print('hello')"}],
    }
    response = await client.post("/api/v1/submissions", json=submission_data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_get_submission(client):
    """Test creating and retrieving a submission."""
    config_data = {
        "external_assignment_id": "test-assignment-submit",
        "definition": definition(),
    }
    await client.post("/api/v1/configs", json=config_data)
    mock_grading_tasks = set()
    with patch(
        "web.api.v1.submissions.grade_submission", new_callable=AsyncMock
    ), patch(
        "web.api.v1.submissions.get_grading_tasks", return_value=mock_grading_tasks
    ):
        submission_data = {
            "external_assignment_id": "test-assignment-submit",
            "external_user_id": "user-456",
            "username": "johndoe",
            "files": [{"filename": "main.py", "content": "print('hello world')"}],
            "metadata": {"ip": "127.0.0.1"},
        }
        response = await client.post("/api/v1/submissions", json=submission_data)
        assert response.status_code == 200
        data = response.json()
        assert data["external_user_id"] == "user-456"
        assert data["username"] == "johndoe"
        assert data["status"] == "pending"
        submission_id = data["id"]
        response = await client.get(f"/api/v1/submissions/{submission_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == submission_id
        assert "submission_files" not in data


@pytest.mark.asyncio
async def test_get_user_submissions(client):
    """Test getting all submissions for a user."""
    config_data = {
        "external_assignment_id": "test-assignment-user",
        "definition": definition(),
    }
    await client.post("/api/v1/configs", json=config_data)
    mock_grading_tasks = set()
    with patch(
        "web.api.v1.submissions.grade_submission", new_callable=AsyncMock
    ), patch(
        "web.api.v1.submissions.get_grading_tasks", return_value=mock_grading_tasks
    ):
        user_id = "user-789"
        for i in range(3):
            submission_data = {
                "external_assignment_id": "test-assignment-user",
                "external_user_id": user_id,
                "username": "janedoe",
                "files": [
                    {"filename": "main.py", "content": f"print('submission {i}')"}
                ],
            }
            await client.post("/api/v1/submissions", json=submission_data)
        response = await client.get(f"/api/v1/submissions/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


@pytest.mark.asyncio
async def test_duplicate_config_fails(client):
    """Test that creating duplicate config fails."""
    config_data = {
        "external_assignment_id": "test-duplicate",
        "definition": definition(),
    }
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 200
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 409
