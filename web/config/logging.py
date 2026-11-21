"""Logging configuration for the web API (the shared schema is ``sandbox_manager.structured_logging``)."""

import logging

from sandbox_manager.structured_logging import setup_logging as setup_structured_logging


def setup_logging(*, json_logs: bool, service_name: str, app_env: str, log_level: str = "INFO") -> None:
    """Configure the API's structured logs and quiet SQLAlchemy's statement echo."""
    setup_structured_logging(json_logs=json_logs, service_name=service_name, app_env=app_env, log_level=log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
