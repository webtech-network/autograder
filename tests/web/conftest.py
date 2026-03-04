"""Shared test fixtures and configuration for web tests."""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from web.database.base import Base
from web.database import session


@pytest.fixture(scope="session", autouse=True)
def mock_external_dependencies():
    """
    Mock external dependencies that require Docker or external services.

    This fixture is automatically used for all tests to avoid requiring
    Docker containers or external services during testing.
    """
    with patch("web.core.lifespan.initialize_sandbox_manager"), \
         patch("web.core.lifespan.TemplateLibraryService") as mock_template_lib, \
         patch("web.core.lifespan.SandboxPoolConfig.load_from_yaml") as mock_load_yaml:

        # Mock template library service
        mock_template_service = Mock()
        mock_template_service.get_all_templates_info = Mock(return_value=[
            {
                "name": "webdev",
                "description": "Web development grading",
                "supported_languages": ["python", "javascript", "html"]
            },
            {
                "name": "input_output",
                "description": "Input/output testing",
                "supported_languages": ["python", "java", "cpp"]
            },
            {
                "name": "api_testing",
                "description": "API testing",
                "supported_languages": ["python", "javascript", "java"]
            }
        ])

        mock_template_service.get_template_info = Mock(side_effect=lambda name: {
            "name": name,
            "description": f"{name} template",
            "supported_languages": ["python", "java"]
        })

        mock_template_lib.get_instance.return_value = mock_template_service

        # Mock sandbox config loading
        mock_load_yaml.return_value = []

        yield


@pytest.fixture
async def db_engine():
    """
    Create an in-memory SQLite database engine for testing.

    This provides isolated database for each test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """
    Create a database session for testing.

    Replaces the global session maker with a test-specific one.
    """
    # Store original session maker
    original_session_maker = session.AsyncSessionLocal

    # Create test session maker
    test_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Replace global session maker
    session.AsyncSessionLocal = test_session_maker
    session.engine = db_engine

    # Provide session to test
    async with test_session_maker() as sess:
        yield sess
        # Rollback any uncommitted changes
        await sess.rollback()

    # Restore original session maker
    session.AsyncSessionLocal = original_session_maker


@pytest.fixture
async def test_client(db_engine):
    """
    Create an HTTP test client for the FastAPI application.

    This client can be used to make requests to the API endpoints.
    """
    # Import app here to ensure mocks are in place
    from web.main import app

    # Replace session maker for this test
    original_session_maker = session.AsyncSessionLocal
    session.AsyncSessionLocal = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    session.engine = db_engine

    # Create and yield client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    # Restore original session maker
    session.AsyncSessionLocal = original_session_maker


@pytest.fixture
def sample_config_data():
    """Sample grading configuration data for testing."""
    return {
        "external_assignment_id": "test-assignment-001",
        "template_name": "input_output",
        "languages": ["python"],
        "criteria_config": {
            "base": {
                "tests": [
                    {
                        "name": "test_hello_world",
                        "input": "",
                        "expected_output": "Hello, World!",
                        "weight": 50
                    },
                    {
                        "name": "test_greeting",
                        "input": "Alice",
                        "expected_output": "Hello, Alice!",
                        "weight": 50
                    }
                ]
            }
        },
        "setup_config": {
            "main_file": "main.py",
            "timeout": 5
        }
    }


@pytest.fixture
def sample_submission_data():
    """Sample submission data for testing."""
    return {
        "external_assignment_id": "test-assignment-001",
        "external_user_id": "user_test_001",
        "username": "test_student",
        "files": [
            {
                "filename": "main.py",
                "content": "print('Hello, World!')"
            }
        ],
        "metadata": {
            "ip_address": "127.0.0.1",
            "user_agent": "pytest"
        }
    }

