"""Integration authentication configuration."""

import os


class IntegrationAuthConfig:

    def __init__(self) -> None:
        if "AUTOGRADER_INTEGRATION_TOKEN" not in os.environ:
            raise ValueError(
                "AUTOGRADER_INTEGRATION_TOKEN environment variable must be set"
            )
        self.token: str = os.environ["AUTOGRADER_INTEGRATION_TOKEN"]


integration_auth_config: IntegrationAuthConfig | None = None


def get_integration_auth_config() -> IntegrationAuthConfig:
    global integration_auth_config
    if integration_auth_config is None:
        integration_auth_config = IntegrationAuthConfig()
    return integration_auth_config
