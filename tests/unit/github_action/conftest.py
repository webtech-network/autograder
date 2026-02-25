"""
conftest.py for github_action unit tests.

Patches docker.from_env at the earliest possible point so that importing
sandbox_manager.manager (pulled in transitively by autograder.autograder)
does not attempt a real Docker socket connection during collection.
"""

from unittest.mock import MagicMock, patch

_docker_patcher = patch("docker.from_env", return_value=MagicMock())
_docker_patcher.start()
