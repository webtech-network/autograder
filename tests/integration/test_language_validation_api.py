"""Integration tests for language validation in API endpoints."""

import pytest
from httpx import AsyncClient

from web.main import app


@pytest.mark.asyncio
class TestLanguageValidationAPI:
    """Test language validation through API endpoints."""

    async def test_create_config_with_valid_language(self):
        """Test creating a configuration with a valid language."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-valid-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "python"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "python"
            assert data["external_assignment_id"] == "test-valid-lang-001"

    async def test_create_config_with_invalid_language(self):
        """Test that creating a configuration with invalid language fails."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-invalid-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "javascript"  # Should be "node"
                }
            )

            assert response.status_code == 422  # Validation error
            error_data = response.json()
            assert "detail" in error_data
            # Check that the error mentions language validation
            error_msg = str(error_data["detail"])
            assert "language" in error_msg.lower() or "Unsupported" in error_msg

    async def test_create_config_with_case_insensitive_language(self):
        """Test that language validation is case-insensitive."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-case-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "PYTHON"  # Uppercase
                }
            )

            assert response.status_code == 200
            data = response.json()
            # Should be normalized to lowercase
            assert data["language"] == "python"

    async def test_create_config_with_node_instead_of_javascript(self):
        """Test that 'node' is accepted as valid language."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-node-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "node"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "node"

    async def test_create_config_with_empty_language(self):
        """Test that empty language is rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-empty-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": ""
                }
            )

            assert response.status_code == 422  # Validation error

    async def test_update_config_with_invalid_language(self):
        """Test that updating with invalid language fails."""
        # First create a valid config
        async with AsyncClient(app=app, base_url="http://test") as client:
            create_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-update-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "python"
                }
            )
            assert create_response.status_code == 200
            config_id = create_response.json()["id"]

            # Try to update with invalid language
            update_response = await client.put(
                f"/api/v1/configs/{config_id}",
                json={
                    "language": "ruby"  # Invalid
                }
            )

            assert update_response.status_code == 422  # Validation error

    async def test_submit_with_invalid_language_override(self):
        """Test that submission with invalid language override fails."""
        # First create a valid config
        async with AsyncClient(app=app, base_url="http://test") as client:
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-submit-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "python"
                }
            )
            assert config_response.status_code == 200

            # Try to submit with invalid language override
            submit_response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "test-submit-lang-001",
                    "external_user_id": "user-001",
                    "username": "testuser",
                    "files": [
                        {
                            "filename": "test.js",
                            "content": "console.log('hello')"
                        }
                    ],
                    "language": "javascript"  # Should be "node"
                }
            )

            assert submit_response.status_code == 422  # Validation error

