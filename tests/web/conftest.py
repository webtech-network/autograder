"""Each HTTP test composes an isolated app and session factory."""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from web.database.base import Base
from web.database import models  # register tables
from web.core.config import Settings


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def application(session_factory, tmp_path):
    from web.main import create_app
    from autograder.models.capabilities import HostCapabilities

    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts")),
                     session_factory=session_factory, capabilities=HostCapabilities(), start_workers=False)
    app.state.host.ready = True
    yield app
    await app.state.host.close()


@pytest.fixture
async def test_client(application):
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        yield client


@pytest.fixture
async def client(test_client):
    yield test_client


@pytest.fixture
def sample_config_data():
    from tests.web.test_contracts_v1 import definition
    return {"external_assignment_id": "test-assignment-001", "definition": definition()}


@pytest.fixture
def sample_submission_data():
    return {"external_assignment_id": "test-assignment-001", "external_user_id": "user_test_001",
            "username": "test_student", "files": [{"filename": "main.py", "content": "print('Hello, World!')"}],
            "metadata": {"ip_address": "127.0.0.1", "user_agent": "pytest"}}
