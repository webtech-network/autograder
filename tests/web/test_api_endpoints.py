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

# Mock the sandbox manager before importing main
with patch("web.main.initialize_sandbox_manager"), \
     patch("web.main.TemplateLibraryService"):
    from web.main import app

from web.database.base import Base
from web.database import session


@pytest.fixture
async def test_db():
    """Create a fresh test database for each test."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Replace the global session maker
    old_session_maker = session.AsyncSessionLocal
    session.AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session.engine = engine
    
    yield engine
    
    # Restore original session maker
    session.AsyncSessionLocal = old_session_maker
    
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """Create test client."""
    # Create async client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
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
    # Should be ready even without real templates (mocked)
    assert response.status_code in [200, 503]
    data = response.json()
    assert "ready" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_create_grading_config(client):
    """Test creating a grading configuration."""
    config_data = {
        "external_assignment_id": "test-assignment-1",
        "template_name": "webdev",
        "language": "python",
        "criteria_config": {
            "tests": ["test_homepage", "test_navigation"]
        }
    }
    
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 200
    data = response.json()
    assert data["external_assignment_id"] == "test-assignment-1"
    assert data["template_name"] == "webdev"
    assert data["language"] == "python"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_grading_config(client):
    """Test retrieving a grading configuration."""
    # First create a config
    config_data = {
        "external_assignment_id": "test-assignment-2",
        "template_name": "api",
        "language": "javascript",
        "criteria_config": {"tests": ["test_api"]}
    }
    await client.post("/api/v1/configs", json=config_data)
    
    # Then retrieve it
    response = await client.get("/api/v1/configs/test-assignment-2")
    assert response.status_code == 200
    data = response.json()
    assert data["external_assignment_id"] == "test-assignment-2"
    assert data["template_name"] == "api"


@pytest.mark.asyncio
async def test_list_grading_configs(client):
    """Test listing grading configurations."""
    # Create multiple configs
    for i in range(3):
        config_data = {
            "external_assignment_id": f"test-assignment-list-{i}",
            "template_name": "webdev",
            "language": "python",
            "criteria_config": {"tests": [f"test{i}"]}
        }
        await client.post("/api/v1/configs", json=config_data)
    
    # List them
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
        "files": {"main.py": "print('hello')"}
    }
    
    response = await client.post("/api/v1/submissions", json=submission_data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_get_submission(client):
    """Test creating and retrieving a submission."""
    # First create a config
    config_data = {
        "external_assignment_id": "test-assignment-submit",
        "template_name": "webdev",
        "language": "python",
        "criteria_config": {"tests": ["test1"]}
    }
    await client.post("/api/v1/configs", json=config_data)
    
    # Create submission
    submission_data = {
        "external_assignment_id": "test-assignment-submit",
        "external_user_id": "user-456",
        "username": "johndoe",
        "files": {"main.py": "print('hello world')"},
        "metadata": {"ip": "127.0.0.1"}
    }
    
    response = await client.post("/api/v1/submissions", json=submission_data)
    assert response.status_code == 200
    data = response.json()
    assert data["external_user_id"] == "user-456"
    assert data["username"] == "johndoe"
    assert data["status"] == "pending"
    
    submission_id = data["id"]
    
    # Get submission
    response = await client.get(f"/api/v1/submissions/{submission_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == submission_id
    assert data["submission_files"]["main.py"] == "print('hello world')"


@pytest.mark.asyncio
async def test_get_user_submissions(client):
    """Test getting all submissions for a user."""
    # Create config
    config_data = {
        "external_assignment_id": "test-assignment-user",
        "template_name": "webdev",
        "language": "python",
        "criteria_config": {"tests": ["test1"]}
    }
    await client.post("/api/v1/configs", json=config_data)
    
    # Create multiple submissions for same user
    user_id = "user-789"
    for i in range(3):
        submission_data = {
            "external_assignment_id": "test-assignment-user",
            "external_user_id": user_id,
            "username": "janedoe",
            "files": {"main.py": f"print('submission {i}')"}
        }
        await client.post("/api/v1/submissions", json=submission_data)
    
    # Get user submissions
    response = await client.get(f"/api/v1/submissions/user/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_duplicate_config_fails(client):
    """Test that creating duplicate config fails."""
    config_data = {
        "external_assignment_id": "test-duplicate",
        "template_name": "webdev",
        "language": "python",
        "criteria_config": {"tests": ["test1"]}
    }
    
    # First creation should succeed
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 200
    
    # Second creation should fail
    response = await client.post("/api/v1/configs", json=config_data)
    assert response.status_code == 400
