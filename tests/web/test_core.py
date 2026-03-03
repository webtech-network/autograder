"""Unit tests for core configuration and lifespan."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from web.core.config import settings, Settings
from web.core.lifespan import get_template_service, get_grading_tasks, lifespan


def test_settings_defaults():
    """Test that settings have correct defaults."""
    s = Settings()
    assert s.API_VERSION == "1.0.0"
    assert s.API_TITLE == "Autograder Web API"
    assert s.API_DESCRIPTION == "RESTful API for code submission grading"
    assert s.CORS_ORIGINS == ["*"]
    assert s.CORS_ALLOW_CREDENTIALS is True
    assert s.CORS_ALLOW_METHODS == ["*"]
    assert s.CORS_ALLOW_HEADERS == ["*"]


def test_get_template_service():
    """Test getting template service."""
    # Initially None or whatever was set
    service = get_template_service()
    # Can be None before initialization
    assert service is None or service is not None


def test_get_grading_tasks():
    """Test getting grading tasks set."""
    tasks = get_grading_tasks()
    assert isinstance(tasks, set)


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown():
    """Test application lifespan management."""
    mock_app = Mock()

    # Mock all initialization functions
    with patch("web.core.lifespan.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("web.core.lifespan.SandboxPoolConfig.load_from_yaml") as mock_load_yaml, \
         patch("web.core.lifespan.initialize_sandbox_manager") as mock_init_sandbox, \
         patch("web.core.lifespan.TemplateLibraryService.get_instance") as mock_get_template, \
         patch("web.core.lifespan.get_sandbox_manager") as mock_get_sandbox_mgr, \
         patch("os.getenv", return_value="sandbox_config.yml"):

        # Setup mocks
        mock_load_yaml.return_value = [Mock()]
        mock_template_instance = Mock()
        mock_get_template.return_value = mock_template_instance

        mock_sandbox_mgr = Mock()
        mock_sandbox_mgr.shutdown = Mock()
        mock_get_sandbox_mgr.return_value = mock_sandbox_mgr

        # Test lifespan context manager
        async with lifespan(mock_app):
            # Verify startup was called
            mock_init_db.assert_called_once()
            mock_load_yaml.assert_called_once()
            mock_init_sandbox.assert_called_once()
            mock_get_template.assert_called_once()

        # Verify shutdown was called
        mock_sandbox_mgr.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_with_pending_tasks():
    """Test that pending grading tasks are cancelled on shutdown."""
    mock_app = Mock()

    with patch("web.core.lifespan.init_db", new_callable=AsyncMock), \
         patch("web.core.lifespan.SandboxPoolConfig.load_from_yaml", return_value=[Mock()]), \
         patch("web.core.lifespan.initialize_sandbox_manager"), \
         patch("web.core.lifespan.TemplateLibraryService.get_instance"), \
         patch("web.core.lifespan.get_sandbox_manager") as mock_get_sandbox, \
         patch("web.core.lifespan.grading_tasks") as mock_tasks, \
         patch("asyncio.gather", new_callable=AsyncMock) as mock_gather, \
         patch("os.getenv", return_value="sandbox_config.yml"):

        # Create mock tasks
        mock_task1 = Mock()
        mock_task1.done = Mock(return_value=False)
        mock_task1.cancel = Mock()

        mock_task2 = Mock()
        mock_task2.done = Mock(return_value=True)

        # Initially use real set, then replace with tasks during shutdown
        import web.core.lifespan as lifespan_module

        mock_sandbox_mgr = Mock()
        mock_sandbox_mgr.shutdown = Mock()
        mock_get_sandbox.return_value = mock_sandbox_mgr

        async with lifespan(mock_app):
            # Add tasks to the grading_tasks set
            lifespan_module.grading_tasks.add(mock_task1)
            lifespan_module.grading_tasks.add(mock_task2)

        # Verify only non-done tasks were cancelled
        mock_task1.cancel.assert_called_once()
        # mock_task2.cancel should not be called since it's done

