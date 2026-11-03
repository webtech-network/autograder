"""One host-owned sandbox manager per integration test process.

The manager uses the test process's own lease directory (see tests/conftest.py),
so its startup reclamation can never select another host's containers.
"""
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from autograder.models.language import Language
from tests.sandbox_profiles import TEST_IMAGES

_CURRENT = None


def start_test_manager(pool_configs):
    """Replace the shared manager (shutting the previous one down) and start it."""
    global _CURRENT  # pylint: disable=global-statement
    shutdown_test_manager()
    _CURRENT = SandboxManager(pool_configs).start()
    return _CURRENT


def current_test_manager():
    if _CURRENT is None:
        return start_test_manager([
            SandboxPoolConfig(language=language, image=TEST_IMAGES[language], pool_size=1, scale_limit=4, idle_timeout=300, running_timeout=120)
            for language in (Language.PYTHON, Language.JAVA, Language.NODE, Language.CPP)])
    return _CURRENT


def shutdown_test_manager():
    global _CURRENT  # pylint: disable=global-statement
    if _CURRENT is not None:
        manager, _CURRENT = _CURRENT, None
        manager.shutdown()
