"""Integration authentication configuration."""

import os


class IntegrationAuthConfig:

    def __init__(self) -> None:
        if "AUTOGRADER_INTEGRATION_TOKEN" not in os.environ:
            raise ValueError(
                "AUTOGRADER_INTEGRATION_TOKEN environment variable must be set"
            )
        token = os.environ["AUTOGRADER_INTEGRATION_TOKEN"].strip()
        if not token:
            raise ValueError(
                "AUTOGRADER_INTEGRATION_TOKEN environment variable must be non-empty"
            )
        self.token: str = token


integration_auth_config: IntegrationAuthConfig | None = None


def get_integration_auth_config() -> IntegrationAuthConfig:
    global integration_auth_config
    if integration_auth_config is None:
        integration_auth_config = IntegrationAuthConfig()
    return integration_auth_config
