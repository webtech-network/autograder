"""Read host settings once, at application construction."""
import os
from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True)
class Settings:
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "Autograder Web API"
    API_DESCRIPTION: str = "RESTful API for code submission grading"
    CORS_ORIGINS: list[str] = field(default_factory=lambda: ["*"])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = field(default_factory=lambda: ["*"])
    CORS_ALLOW_HEADERS: list[str] = field(default_factory=lambda: ["*"])
    JSON_LOGS: bool = field(default_factory=lambda: os.getenv("JSON_LOGS", "false").lower() == "true")
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    SERVICE_NAME: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "autograder-api"))
    APP_ENV: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder"))
    DATABASE_ECHO: bool = field(default_factory=lambda: os.getenv("DATABASE_ECHO", "false").lower() == "true")
    DATABASE_POOL_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10")))
    DATABASE_MAX_OVERFLOW: int = field(default_factory=lambda: int(os.getenv("DATABASE_MAX_OVERFLOW", "20")))
    DATABASE_POOL_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_TIMEOUT", "30")))
    DATABASE_POOL_RECYCLE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_RECYCLE", "3600")))
    INTEGRATION_TOKEN: str = field(default_factory=lambda: os.getenv("AUTOGRADER_INTEGRATION_TOKEN", ""))
    RECEIPT_DIR: str = field(default_factory=lambda: os.getenv("WEB_OUTCOME_RECEIPT_DIR", "data/unpublished-outcomes"))
    WORKER_COUNT: int = field(default_factory=lambda: int(os.getenv("WEB_WORKER_COUNT", "2")))
    LEASE_SECONDS: float = field(default_factory=lambda: float(os.getenv("WEB_LEASE_SECONDS", "60")))
    MAX_ATTEMPTS: int = field(default_factory=lambda: int(os.getenv("WEB_MAX_ATTEMPTS", "3")))
    POLL_SECONDS: float = field(default_factory=lambda: float(os.getenv("WEB_POLL_SECONDS", "1")))
    SANDBOX_CONFIG_FILE: str = field(default_factory=lambda: os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
    SANDBOX_MODE: str = field(default_factory=lambda: os.getenv("SANDBOX_MODE", "local"))
    SANDBOX_API_URL: str = field(default_factory=lambda: os.getenv("SANDBOX_API_URL", "http://localhost:8001"))

    def __post_init__(self):
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must not be empty")
        if self.WORKER_COUNT < 1 or self.MAX_ATTEMPTS < 1:
            raise ValueError("Worker count and attempt budget must be positive")
        if not all(isfinite(value) and value > 0 for value in (self.LEASE_SECONDS, self.POLL_SECONDS)):
            raise ValueError("Worker lease and polling intervals must be positive")
        if self.SANDBOX_MODE not in ("local", "remote"):
            raise ValueError("SANDBOX_MODE must be local or remote")
        if min(self.DATABASE_POOL_SIZE, self.DATABASE_POOL_TIMEOUT, self.DATABASE_POOL_RECYCLE) <= 0 or self.DATABASE_MAX_OVERFLOW < 0:
            raise ValueError("Database pool settings must be positive; overflow may be zero")
