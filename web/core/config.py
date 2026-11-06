"""Read the API host's settings once, at application construction.

This module and the execution providers it composes (``execution_host``) are the
API's only readers of the environment; ``docs/operate/configuration.md`` lists
every variable, and ``tests/unit/test_settings_contract.py`` keeps the two equal.
Incoherent or retired configuration raises :class:`ValueError` naming the
variable, so the process refuses to start instead of failing while grading.
"""
import os
import re
from dataclasses import dataclass, field
from math import isfinite

_PRODUCER_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,62}")
_FLAGS = {"1": True, "true": True, "yes": True, "0": False, "false": False, "no": False}

#: Names this host no longer reads, with what replaced them. Setting one to a
#: non-empty value stops startup, so a stale deployment cannot silently lose a feature.
RETIRED = {
    "SANDBOX_POOL_SIZE": "the host-wide sandbox budget is general.max_sandboxes in sandbox_config.yml "
                         "(SANDBOX_CONFIG_FILE); warm containers are general.pool_size there",
    "API_HOST": "the image serves on 0.0.0.0:8000; choose the published address in your Compose ports",
    "API_PORT": "the image serves on 0.0.0.0:8000; choose the published port in your Compose ports",
    "API_WORKERS": "run one API process per container and scale with WEB_WORKER_COUNT",
    "UPSTASH_REDIS_URL": "the Upstash exporter was removed; outcomes are stored in PostgreSQL",
    "UPSTASH_REDIS_TOKEN": "the Upstash exporter was removed; outcomes are stored in PostgreSQL",
    "CRITERIA_ASSETS_BUCKET_NAME": "renamed EXTERNAL_ASSETS_BUCKET_NAME",
    "AWS_ACCESS_ID": "use AWS_ACCESS_KEY_ID",
}


def reject_retired(retired, environ=None):
    """Raise when any retired name is set, with every offending name and its replacement."""
    present = {name: value for name, value in (os.environ if environ is None else environ).items()
               if name in retired and value.strip()}
    if present:
        raise ValueError("Retired configuration is set; unset it: " + "; ".join(
            f"{name}: {retired[name]}" for name in sorted(present)))


def _text(name, default):
    return os.environ.get(name, default)


def _flag(name, default):
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return _FLAGS[value.strip().lower()]
    except KeyError:
        raise ValueError(f"{name} must be true or false, got {value!r}") from None


def _number(name, default, kind=int):
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return kind(value)
    except ValueError:
        raise ValueError(f"{name} must be a{'n integer' if kind is int else ' number'}, got {value!r}") from None


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
    JSON_LOGS: bool = field(default_factory=lambda: _flag("JSON_LOGS", False))
    LOG_LEVEL: str = field(default_factory=lambda: _text("LOG_LEVEL", "INFO"))
    SERVICE_NAME: str = field(default_factory=lambda: _text("SERVICE_NAME", "autograder-api"))
    APP_ENV: str = field(default_factory=lambda: _text("APP_ENV", "local"))
    DATABASE_URL: str = field(default_factory=lambda: _text(
        "DATABASE_URL", "postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder"))
    DATABASE_ECHO: bool = field(default_factory=lambda: _flag("DATABASE_ECHO", False))
    DATABASE_POOL_SIZE: int = field(default_factory=lambda: _number("DATABASE_POOL_SIZE", 10))
    DATABASE_MAX_OVERFLOW: int = field(default_factory=lambda: _number("DATABASE_MAX_OVERFLOW", 20))
    DATABASE_POOL_TIMEOUT: int = field(default_factory=lambda: _number("DATABASE_POOL_TIMEOUT", 30))
    DATABASE_POOL_RECYCLE: int = field(default_factory=lambda: _number("DATABASE_POOL_RECYCLE", 3600))
    INTEGRATION_TOKEN: str = field(default_factory=lambda: _text("AUTOGRADER_INTEGRATION_TOKEN", ""))
    ATTESTATION_TOKENS: dict[str, str] = field(
        default_factory=lambda: parse_attestation_tokens(_text("AUTOGRADER_ATTESTATION_TOKENS", "")))
    RECEIPT_DIR: str = field(default_factory=lambda: _text("WEB_OUTCOME_RECEIPT_DIR", "data/unpublished-outcomes"))
    WORKER_COUNT: int = field(default_factory=lambda: _number("WEB_WORKER_COUNT", 2))
    LEASE_SECONDS: float = field(default_factory=lambda: _number("WEB_LEASE_SECONDS", 60.0, float))
    MAX_ATTEMPTS: int = field(default_factory=lambda: _number("WEB_MAX_ATTEMPTS", 3))
    POLL_SECONDS: float = field(default_factory=lambda: _number("WEB_POLL_SECONDS", 1.0, float))
    SANDBOX_CONFIG_FILE: str = field(default_factory=lambda: _text("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
    # The API owns its sandboxes in-process unless told to use a sandbox manager.
    SANDBOX_MODE: str = field(default_factory=lambda: _text("SANDBOX_MODE", "local"))
    SANDBOX_API_URL: str = field(default_factory=lambda: _text("SANDBOX_API_URL", "http://localhost:8001"))
    # Bearer token for the private sandbox control API (remote mode only).
    SANDBOX_API_TOKEN: str = field(default_factory=lambda: _text("SANDBOX_API_TOKEN", ""), repr=False)

    def __post_init__(self):
        reject_retired(RETIRED)
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
            raise ValueError(f"SANDBOX_MODE must be local or remote, got {self.SANDBOX_MODE!r}")
        if self.LOG_LEVEL.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL, got {self.LOG_LEVEL!r}")
        if min(self.DATABASE_POOL_SIZE, self.DATABASE_POOL_TIMEOUT, self.DATABASE_POOL_RECYCLE) <= 0 or self.DATABASE_MAX_OVERFLOW < 0:
            raise ValueError("Database pool settings must be positive; overflow may be zero")
