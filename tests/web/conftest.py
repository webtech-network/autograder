"""Each HTTP test composes an isolated app and session factory."""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from autograder.models.capabilities import HostCapabilities
from web.database.base import Base
from web.database import models  # pylint: disable=unused-import  # Register tables.
from web.core.config import Settings


@pytest.fixture
async def db_engine(tmp_path):
    """Give concurrent HTTP and worker sessions independent connections."""
    # HTTP requests and worker claims need independent transactions. An in-memory
    # StaticPool shares one connection, so closing a reader can undo a writer.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'web.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    """Bind sessions to this test's database."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    """Roll back any unfinished transaction when the test releases its session."""
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def application(session_factory, tmp_path):
    """Compose an app after the test's environment fixtures have run."""
    from web.main import create_app

    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts")),
                     session_factory=session_factory, capabilities=HostCapabilities(), start_workers=False)
    app.state.host.ready = True
    yield app
    await app.state.host.close()


@pytest.fixture
async def test_client(application):
    """Send HTTP requests through the real application without a network server."""
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        yield client


@pytest.fixture
async def client(test_client):
    """Retain the short fixture name used by contract tests."""
    yield test_client


@pytest.fixture
def sample_config_data():
    """Supply a valid configuration envelope for route tests."""
    from tests.web.test_contracts_v1 import definition
    return {"external_assignment_id": "test-assignment-001", "definition": definition()}


@pytest.fixture
def sample_submission_data():
    """Supply a small valid submission with host audit metadata."""
    return {"external_assignment_id": "test-assignment-001", "external_user_id": "user_test_001",
            "username": "test_student", "files": [{"filename": "main.py", "content": "print('Hello, World!')"}],
            "metadata": {"ip_address": "127.0.0.1", "user_agent": "pytest"}}
