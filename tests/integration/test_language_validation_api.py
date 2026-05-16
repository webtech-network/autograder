import uuid
"""Integration tests for language validation in API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

from web.main import app


@pytest.mark.asyncio
class TestLanguageValidationAPI:
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

    async def test_create_config_with_valid_languages(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assignment_id = "val-lang-" + str(uuid.uuid4())[:8]
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": assignment_id,
                    "template_name": "input_output",
                    "criteria_config": {"test_library": "input_output", "base": {"weight": 100, "tests": []}},
                    "languages": ["python", "java"]
                }
            )
            assert response.status_code == 200

    async def test_create_config_with_invalid_language(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "val-lang-" + str(uuid.uuid4())[:8],
                    "template_name": "input_output",
                    "criteria_config": {"test_library": "input_output", "base": {"weight": 100, "tests": []}},
                    "languages": ["python", "rust"]
                }
            )
            assert response.status_code == 422
