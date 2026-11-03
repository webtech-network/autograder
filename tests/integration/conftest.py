"""Integration hosts own their sandbox manager lifetime explicitly."""
import pytest

from tests.integration.sandbox_support import shutdown_test_manager


@pytest.fixture(scope="session", autouse=True)
def _shutdown_shared_sandbox_manager():
    yield
    shutdown_test_manager()
