"""Database configuration."""

import os
from typing import Optional


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./autograder.db")
        self.echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
        self.pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
        self.max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
        self.pool_timeout: int = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
        self.pool_recycle: int = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return "sqlite" in self.url

    def __repr__(self):
        return f"<DatabaseConfig(url={self.url}, echo={self.echo})>"


# Global config instance
db_config = DatabaseConfig()
