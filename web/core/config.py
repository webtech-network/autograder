"""Application configuration."""

settings = Settings()


    SANDBOX_CONFIG_FILE: str = os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml")
    # Sandbox Configuration

    JSON_LOGS: bool = os.getenv("JSON_LOGS", "false").lower() == "true"
    # Logging Configuration

    CORS_ALLOW_HEADERS: list = ["*"]
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ORIGINS: list = ["*"]  # In production, replace with specific origins
    # CORS Configuration

    API_DESCRIPTION: str = "RESTful API for code submission grading"
    API_TITLE: str = "Autograder Web API"
    API_VERSION: str = "1.0.0"
    # API Configuration

    """Application settings."""
class Settings:


from typing import Optional
import os

