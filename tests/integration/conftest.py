"""The test session is the host: it shuts down any shared sandbox manager."""
import pytest

from tests.integration import sandbox_support


@pytest.fixture(scope="session", autouse=True)
def _shutdown_shared_sandbox_manager():
    yield
    sandbox_support.shutdown_manager()
