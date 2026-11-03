"""Read host settings once, at application construction."""
import os
import re
from dataclasses import dataclass, field
from math import isfinite

_PRODUCER_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,62}")


def parse_attestation_tokens(value: str) -> dict[str, str]:
    """Parse `name=token,name2=token2` restricted producer credentials."""
    tokens = {}
    for entry in filter(None, (part.strip() for part in value.split(","))):
        name, separator, token = entry.partition("=")
        name, token = name.strip(), token.strip()
        if not separator or not token:
            raise ValueError("AUTOGRADER_ATTESTATION_TOKENS entries must be name=token")
        if name in tokens:
            raise ValueError(f"Duplicate attestation producer name: {name}")
        tokens[name] = token
    return tokens


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
    ATTESTATION_TOKENS: dict[str, str] = field(
        default_factory=lambda: parse_attestation_tokens(os.getenv("AUTOGRADER_ATTESTATION_TOKENS", "")))
    RECEIPT_DIR: str = field(default_factory=lambda: os.getenv("WEB_OUTCOME_RECEIPT_DIR", "data/unpublished-outcomes"))
    WORKER_COUNT: int = field(default_factory=lambda: int(os.getenv("WEB_WORKER_COUNT", "2")))
    LEASE_SECONDS: float = field(default_factory=lambda: float(os.getenv("WEB_LEASE_SECONDS", "60")))
    MAX_ATTEMPTS: int = field(default_factory=lambda: int(os.getenv("WEB_MAX_ATTEMPTS", "3")))
    POLL_SECONDS: float = field(default_factory=lambda: float(os.getenv("WEB_POLL_SECONDS", "1")))
    SANDBOX_CONFIG_FILE: str = field(default_factory=lambda: os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
    SANDBOX_MODE: str = field(default_factory=lambda: os.getenv("SANDBOX_MODE", "local"))
    SANDBOX_API_URL: str = field(default_factory=lambda: os.getenv("SANDBOX_API_URL", "http://localhost:8001"))
    # Bearer token for the private sandbox control API (remote mode only).
    SANDBOX_API_TOKEN: str = field(default_factory=lambda: os.getenv("SANDBOX_API_TOKEN", ""), repr=False)

    def __post_init__(self):
        tokens = [self.INTEGRATION_TOKEN.strip()] if self.INTEGRATION_TOKEN.strip() else []
        for name, token in self.ATTESTATION_TOKENS.items():
            if not _PRODUCER_NAME.fullmatch(name):
                raise ValueError(f"Invalid attestation producer name: {name!r}")
            if not token.strip():
                raise ValueError(f"Attestation producer {name!r} has an empty token")
            tokens.append(token.strip())
        if len(tokens) != len(set(tokens)):
            raise ValueError("Every integration/attestation credential must be distinct")
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
