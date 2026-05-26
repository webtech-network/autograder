"""Application lifespan management."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI

from autograder.services.template_library_service import TemplateLibraryService
from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from web.config.logging import get_logger
from web.core.config import settings
from web.database import init_db


logger = get_logger(__name__)

# Global state
template_service: Optional[TemplateLibraryService] = None
grading_tasks: set = set()  # Track active grading tasks to prevent garbage collection


def get_template_service() -> Optional[TemplateLibraryService]:
    """Get the template service instance."""
    return template_service


def get_grading_tasks() -> set:
    """Get the set of active grading tasks."""
    return grading_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: startup and shutdown.

    Startup:
    - Initialize database
    - Initialize sandbox manager
    - Load template library

    Shutdown:
    - Clean up resources
    """
    _ = app # unused argument

    load_dotenv()  # Load environment variables first from .env file

    global template_service, grading_tasks

    # Startup
    logger.info("Starting Autograder Web API...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

    # Initialize sandbox manager
    logger.info("Initializing sandbox manager...")

    if settings.SANDBOX_MODE == "remote":
        pool_configs = []
        logger.info("Sandbox configured for remote mode, skipping local pool configuration")
    else:
        config_file = settings.SANDBOX_CONFIG_FILE
        try:
            pool_configs = SandboxPoolConfig.load_from_yaml(config_file)
            logger.info("Loaded sandbox configurations from %s", config_file)
        except FileNotFoundError as e:
            logger.error("Sandbox configuration file not found: %s", e)
            raise
        except Exception as e:
            logger.error("Error loading sandbox configuration: %s", e)
            raise

    initialize_sandbox_manager(
        pool_configs=pool_configs,
        mode=settings.SANDBOX_MODE,
        api_url=settings.SANDBOX_API_URL
    )
    logger.info("Sandbox manager initialized in %s mode", settings.SANDBOX_MODE)

    # Initialize template library
    logger.info("Loading template library...")
    template_service = TemplateLibraryService.get_instance()
    logger.info("Template library loaded successfully")

    logger.info("Autograder Web API ready!")

    yield

    # Shutdown
    logger.info("Shutting down Autograder Web API...")

    # Cancel pending grading tasks
    if grading_tasks:
        logger.info("Cancelling %s pending grading tasks...", len(grading_tasks))
        for task in grading_tasks:
            if not task.done():
                task.cancel()
        # Wait for tasks to complete cancellation
        if grading_tasks:
            await asyncio.gather(*grading_tasks, return_exceptions=True)
        logger.info("All pending grading tasks cancelled")

    # Explicitly shutdown sandbox manager to clean up resources (containers or HTTP sessions)
    try:
        manager = get_sandbox_manager()
        logger.info("Shutting down sandbox manager...")
        manager.shutdown()
        logger.info("Sandbox manager shutdown complete")
    except Exception as e:
        logger.error("Error during sandbox manager shutdown: %s", e)

    logger.info("Shutdown complete")

