"""Logging configuration for the web API."""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict

from web.config.request_context import get_request_id


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def __init__(self, service_name: str, app_env: str):
        super().__init__()
        self._service_name = service_name
        self._app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service_name,
            "env": self._app_env,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add contextual fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "method"):
            log_data["method"] = record.method

        if hasattr(record, "path"):
            log_data["path"] = record.path

        if hasattr(record, "status"):
            log_data["status"] = record.status

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)


class RequestContextFilter(logging.Filter):
    """Inject async request context into all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = get_request_id()
        record.request_id = request_id or "-"
        return True


def setup_logging(
    json_logs: bool = False,
    service_name: str = "autograder-api",
    app_env: str = "local",
    log_level: str = "INFO",
) -> None:
    """
    Setup application logging.

    Args:
        json_logs: If True, use JSON formatter for structured logs.
                  If False, use human-readable format.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())

    # Set formatter
    if json_logs:
        formatter = JSONFormatter(service_name=service_name, app_env=app_env)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [request_id=%(request_id)s] %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Route uvicorn logs to root handler so JSON/human format stays consistent
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
