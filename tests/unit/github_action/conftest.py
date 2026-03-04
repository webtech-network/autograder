"""
conftest.py for github_action unit tests.

Patches docker.from_env at the earliest possible point so that importing
sandbox_manager.manager (pulled in transitively by autograder.autograder)
does not attempt a real Docker socket connection during collection.
"""

from unittest.mock import MagicMock, patch

import pytest

_docker_patcher = patch("docker.from_env", return_value=MagicMock())
_docker_patcher.start()


@pytest.fixture(scope="session", autouse=True)
def _docker_patcher_cleanup():
    """
    Ensure the global docker.from_env patcher started at import time
    is properly stopped after the test session.
    """
    try:
        yield
    finally:
        _docker_patcher.stop()
