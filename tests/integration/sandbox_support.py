"""Test-host ownership of the shared local SandboxManager used by Docker suites.

Real hosts construct and shut down their own manager; these suites share one
per configuration and the integration conftest shuts it down at session end.
"""
from sandbox_manager.manager import SandboxManager

_manager = None


def start_manager(pool_configs):
    """Replace the shared manager (shutting the previous one down)."""
    global _manager
    shutdown_manager()
    _manager = SandboxManager(pool_configs)
    return _manager


def current_manager():
    if _manager is None:
        raise RuntimeError("No shared sandbox manager has been started")
    return _manager


def shutdown_manager():
    global _manager
    if _manager is not None:
        manager, _manager = _manager, None
        manager.shutdown()


def wait_for_idle(pool, expected=None, timeout=20.0):
    """Disposal is immediate; replenishment is the pool monitor's asynchronous job."""
    import time
    expected = pool.config.pool_size if expected is None else expected
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and len(pool.idle_sandboxes) != expected:
        time.sleep(0.2)
    return len(pool.idle_sandboxes)
