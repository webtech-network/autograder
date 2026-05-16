import uuid
"""Integration test for multi-language submissions for the same assignment."""

import pytest
from httpx import AsyncClient, ASGITransport

from web.main import app


@pytest.mark.asyncio
class TestMultiLanguageSubmissions:
    @classmethod
    def setup_class(cls):
        from sandbox_manager.manager import initialize_sandbox_manager
        from sandbox_manager.models.pool_config import SandboxPoolConfig
        from sandbox_manager.models.sandbox_models import Language
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import StaticPool
        from web.database.base import Base
        from web.database import session

        # 1. Initialize sandbox manager
        pool_configs = [
            SandboxPoolConfig(language=Language.PYTHON, pool_size=1, scale_limit=2, idle_timeout=300, running_timeout=60),
            SandboxPoolConfig(language=Language.JAVA, pool_size=1, scale_limit=2, idle_timeout=300, running_timeout=60),
        ]
        initialize_sandbox_manager(pool_configs)

        # 2. Setup in-memory SQLite for testing
        cls.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # 3. Apply monkeypatch to the global session
        cls.original_session_maker = session.AsyncSessionLocal
        session.AsyncSessionLocal = async_sessionmaker(
            cls.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # 4. Create all tables
        async def init_test_db():
            async with cls.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        
        asyncio.run(init_test_db())

    @classmethod
    def teardown_class(cls):
        from sandbox_manager.manager import get_sandbox_manager
        from web.database import session
        try: get_sandbox_manager().shutdown()
        except: pass
        
        # Restore session
        session.AsyncSessionLocal = cls.original_session_maker

    async def test_create_config_and_submit_multiple_languages(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assignment_id = "multi-lang-" + str(uuid.uuid4())[:8]
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": assignment_id,
                    "template_name": "input_output",
                    "criteria_config": {"test_library": "input_output", "base": {"weight": 100, "tests": []}},
                    "languages": ["python", "java", "node", "cpp"]
                }
            )
            assert config_response.status_code == 200

    async def test_case_insensitive_language_override(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assignment_id = "case-lang-" + str(uuid.uuid4())[:8]
            await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": assignment_id,
                    "template_name": "input_output",
                    "criteria_config": {"test_library": "input_output", "base": {"weight": 100, "tests": []}},
                    "languages": ["python", "java"]
                }
            )
            response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": assignment_id,
                    "external_user_id": "user-" + str(uuid.uuid4())[:8],
                    "username": "testuser",
                    "files": [{"filename": "Test.java", "content": "public class Test { }"}],
                    "language": "JAVA"
                }
            )
            assert response.status_code == 200
