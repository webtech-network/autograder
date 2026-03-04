"""Application lifespan management."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

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
    global template_service, grading_tasks

    # Startup
    logger.info("Starting Autograder Web API...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

    # Initialize sandbox manager
    logger.info("Initializing sandbox manager...")

    # Load pool configurations from YAML file
    config_file = settings.SANDBOX_CONFIG_FILE
    try:
        pool_configs = SandboxPoolConfig.load_from_yaml(config_file)
        logger.info(f"Loaded sandbox configurations from {config_file}")
    except FileNotFoundError as e:
        logger.error(f"Sandbox configuration file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading sandbox configuration: {e}")
        raise

    initialize_sandbox_manager(pool_configs)
    logger.info(f"Sandbox manager initialized with {len(pool_configs)} language pools")

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
        logger.info(f"Cancelling {len(grading_tasks)} pending grading tasks...")
        for task in grading_tasks:
            if not task.done():
                task.cancel()
        # Wait for tasks to complete cancellation
        if grading_tasks:
            await asyncio.gather(*grading_tasks, return_exceptions=True)
        logger.info("All pending grading tasks cancelled")

    # Explicitly shutdown sandbox manager to clean up all containers
    try:
        manager = get_sandbox_manager()
        logger.info("Shutting down sandbox manager...")
        manager.shutdown()
        logger.info("Sandbox manager shutdown complete")
    except Exception as e:
        logger.error(f"Error during sandbox manager shutdown: {e}")

    logger.info("Shutdown complete")

