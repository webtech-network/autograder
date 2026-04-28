"""Application configuration."""

import os


class Settings:
    """Application settings."""
    # API Configuration
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "Autograder Web API"
    API_DESCRIPTION: str = "RESTful API for code submission grading"

    # CORS Configuration
    CORS_ORIGINS: list = ["*"]  # In production, replace with specific origins
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    # Logging Configuration
    JSON_LOGS: bool = os.getenv("JSON_LOGS", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "autograder-api")
    APP_ENV: str = os.getenv("APP_ENV", "local")

    # Sandbox Configuration
    SANDBOX_CONFIG_FILE: str = os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml")


settings = Settings()

