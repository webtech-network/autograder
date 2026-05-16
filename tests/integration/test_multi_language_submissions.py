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
        from web.database.session import init_db
        pool_configs = [
            SandboxPoolConfig(language=Language.PYTHON, pool_size=1, scale_limit=2, idle_timeout=300, running_timeout=60),
            SandboxPoolConfig(language=Language.JAVA, pool_size=1, scale_limit=2, idle_timeout=300, running_timeout=60),
        ]
        initialize_sandbox_manager(pool_configs)
        asyncio.run(init_db())

    @classmethod
    def teardown_class(cls):
        from sandbox_manager.manager import get_sandbox_manager
        try: get_sandbox_manager().shutdown()
        except: pass

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
