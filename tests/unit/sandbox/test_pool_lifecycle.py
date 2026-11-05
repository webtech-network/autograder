"""Pool and manager lifecycle against mocked Docker failures."""
import logging
import signal
import threading

import docker
import pytest

from sandbox_manager.docker_profile import container_options
from sandbox_manager.errors import RuntimeUnavailableError, SandboxCapacityTimeout
from sandbox_manager.language_pool import LanguagePool, SandboxBudget, SandboxUnavailableError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.sandbox_models import DisposalStatus, SandboxState
from autograder.models.language import Language
from sandbox_manager.ownership import LABEL_OWNER
from tests.unit.sandbox.fakes import Clock, FakeDocker, owner, pool_config


def make_pool(client=None, clock=None, max_sandboxes=2, **config):
    return LanguagePool(Language.PYTHON, pool_config(**config), client or FakeDocker(), owner(),
                        clock=clock or Clock(), budget=SandboxBudget(max_sandboxes))


def test_dispose_removes_with_force_and_volumes_then_forgets():
    client = FakeDocker()
    pool = make_pool(client)
    sandbox = pool.acquire()
    assert sandbox.state is SandboxState.ACTIVE
    assert pool.dispose(sandbox) is DisposalStatus.DISPOSED
    assert sandbox.container_ref.remove_calls == [{"force": True, "v": True}]
    assert sandbox.state is SandboxState.DISPOSED
    assert client.live == {}
    assert pool.get_stats()["total"] == 0


def test_repeated_dispose_is_a_defined_noop():
    pool = make_pool()
    sandbox = pool.acquire()
    pool.dispose(sandbox)
    assert pool.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
    assert pool.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
    assert len(sandbox.container_ref.remove_calls) == 1


def test_not_found_counts_as_confirmed_removal():
    client = FakeDocker()
    pool = make_pool(client)
    sandbox = pool.acquire()
    del client.live[sandbox.container_ref.id]  # Removed behind our back.
    assert pool.dispose(sandbox) is DisposalStatus.DISPOSED


def test_foreign_sandbox_is_rejected():
    first, second = make_pool(), make_pool()
    sandbox = first.acquire()
    with pytest.raises(ValueError):
        second.dispose(sandbox)


def test_remove_failure_quarantines_and_keeps_capacity(caplog):
    client = FakeDocker()
    clock = Clock()
    pool = make_pool(client, clock, max_sandboxes=1)
    sandbox = pool.acquire()
    sandbox.container_ref.remove_failures = [docker.errors.APIError("daemon busy")]
    with caplog.at_level(logging.ERROR):
        assert pool.dispose(sandbox) is DisposalStatus.QUARANTINED
    assert "SANDBOX QUARANTINED" in caplog.text
    assert sandbox.state is SandboxState.QUARANTINED
    assert sandbox.container_ref.id in client.live          # Not forgotten.
    stats = pool.get_stats()
    assert stats["quarantined"] == 1 and stats["total"] == 1
    assert stats["quarantine"][0]["attempts"] == 1
    assert "daemon busy" in stats["quarantine"][0]["error"]
    with pytest.raises(SandboxCapacityTimeout):
        pool.acquire()                                       # It still holds its budget slot.
    assert pool.dispose(sandbox) is DisposalStatus.QUARANTINED  # Defined, no new attempt.
    assert len(sandbox.container_ref.remove_calls) == 1


def test_quarantine_retry_waits_for_backoff_then_succeeds():
    client = FakeDocker()
    clock = Clock()
    pool = make_pool(client, clock)
    sandbox = pool.acquire()
    sandbox.container_ref.remove_failures = [docker.errors.APIError("x")]
    pool.dispose(sandbox)
    assert pool.retry_quarantined() == []                    # Backoff not elapsed.
    clock.now += 1.5
    assert pool.retry_quarantined() == [DisposalStatus.DISPOSED]
    assert sandbox.state is SandboxState.DISPOSED
    assert pool.get_stats()["quarantined"] == 0
    assert client.live == {}


def test_quarantine_retries_are_bounded_and_stay_visible(caplog):
    client = FakeDocker()
    clock = Clock()
    pool = make_pool(client, clock, disposal_attempts=3)
    sandbox = pool.acquire()
    sandbox.container_ref.remove_failures = [docker.errors.APIError(str(i)) for i in range(10)]
    pool.dispose(sandbox)
    for _ in range(10):
        clock.now += 120
        pool.retry_quarantined()
    assert len(sandbox.container_ref.remove_calls) == 3
    assert "retries exhausted" in caplog.text
    stats = pool.get_stats()
    assert stats["quarantined"] == 1 and stats["quarantine"][0]["exhausted"] is True
    assert stats["total"] == 1


def test_running_timeout_uses_the_disposal_path():
    client = FakeDocker()
    clock = Clock()
    pool = make_pool(client, clock, running_timeout=10)
    sandbox = pool.acquire()
    clock.now += 5
    pool.check_ttls()
    assert sandbox.state is SandboxState.ACTIVE
    clock.now += 6
    sandbox.container_ref.remove_failures = [docker.errors.APIError("x")]
    pool.check_ttls()
    assert sandbox.state is SandboxState.QUARANTINED         # Same path, same failure handling.
    clock.now += 2
    pool.monitor()
    assert sandbox.state is SandboxState.DISPOSED
    assert pool.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED  # Caller's later cleanup.


def test_shutdown_disposes_all_and_reports_failures(caplog):
    client = FakeDocker()
    pool = make_pool(client, pool_size=1, max_sandboxes=3)
    pool.replenish()
    active = pool.acquire()
    stuck = pool.acquire()
    stuck.container_ref.remove_failures = [docker.errors.APIError("a"), docker.errors.APIError("b")]
    with caplog.at_level(logging.ERROR):
        remaining = pool.shutdown()
    assert remaining == 1
    assert active.state is SandboxState.DISPOSED
    assert stuck.state is SandboxState.QUARANTINED
    assert len(stuck.container_ref.remove_calls) == 2         # Dispose plus final shutdown attempt.
    assert list(client.live) == [stuck.container_ref.id]
    assert "unconfirmed" in caplog.text
    with pytest.raises(SandboxUnavailableError):
        pool.acquire()
    pool.replenish()
    assert len(client.live) == 1


def test_gvisor_fallback_only_drops_runtime():
    client = FakeDocker(gvisor=False)
    pool = make_pool(client)
    sandbox = pool.acquire()
    first, second = client.containers.run_calls
    assert first.pop("runtime") == "runsc"
    assert "runtime" not in second
    assert first == second
    assert second["tmpfs"]["/app"].endswith("mode=1777")
    assert second["network_mode"] == "none" and second["cap_drop"] == ["ALL"]
    assert second["labels"][LABEL_OWNER] == "a" * 32
    pool.acquire()
    assert "runtime" not in client.containers.run_calls[-1]  # Unavailable runtime is remembered.
    assert pool.dispose(sandbox) is DisposalStatus.DISPOSED


def test_gvisor_available_uses_runtime():
    client = FakeDocker(gvisor=True)
    make_pool(client).acquire()
    assert [call.get("runtime") for call in client.containers.run_calls] == ["runsc"]


def test_profile_is_declared_once():
    options = container_options("registry.local/java:21", "n", {"k": "v"})
    assert options["image"] == "registry.local/java:21"
    assert options["mem_limit"] == options["memswap_limit"] == "128m"
    assert options["pids_limit"] == 64
    assert options["tmpfs"]["/tmp"].endswith("noexec")


def test_creation_failure_is_unavailable_not_tracked():
    client = FakeDocker(gvisor=True)
    client.run_failure = docker.errors.APIError("image missing")
    pool = make_pool(client)
    with pytest.raises(SandboxUnavailableError):
        pool.acquire()
    assert pool.get_stats()["total"] == 0


# --------------------------------------------------------------------- manager

def test_manager_installs_no_signal_handlers_and_joins_monitor(monkeypatch):
    before = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT))
    import atexit
    registered = []
    monkeypatch.setattr(atexit, "register", registered.append)
    client = FakeDocker()
    manager = SandboxManager([pool_config(pool_size=1)], client, max_sandboxes=2, owner=owner(), monitor_interval=0.01)
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)) == before
    assert registered == []
    assert manager.monitor_thread.is_alive()
    manager.shutdown()
    assert not manager.monitor_thread.is_alive()
    assert client.live == {}
    manager.shutdown()  # Idempotent.
    client.close.assert_not_called()  # Borrowed client stays open.


def test_manager_dispose_and_context_manager():
    client = FakeDocker()
    with SandboxManager([pool_config()], client, max_sandboxes=2, owner=owner(), monitor_interval=60) as manager:
        with manager.acquire_sandbox(Language.PYTHON) as sandbox:
            assert sandbox.state is SandboxState.ACTIVE
        assert sandbox.state is SandboxState.DISPOSED
        assert manager.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
        with pytest.raises(RuntimeUnavailableError):  # no runtime profile: a host capability gap
            manager.get_sandbox(Language.JAVA)
    assert not manager.monitor_thread.is_alive()


def test_manager_shutdown_with_failing_container_completes(caplog):
    client = FakeDocker()
    manager = SandboxManager([pool_config()], client, max_sandboxes=2, owner=owner(), monitor_interval=60)
    sandbox = manager.get_sandbox(Language.PYTHON)
    sandbox.container_ref.remove_failures = [docker.errors.APIError("stuck")] * 5
    manager.shutdown()
    assert sandbox.state is SandboxState.QUARANTINED
    assert manager.get_pool_stats()["python"]["quarantined"] == 1
    assert "unconfirmed" in caplog.text


def test_monitor_retries_quarantine_in_background():
    client = FakeDocker()
    manager = SandboxManager([pool_config()], client, max_sandboxes=2, owner=owner(), monitor_interval=0.01)
    try:
        pool = manager.language_pools[Language.PYTHON]
        sandbox = manager.get_sandbox(Language.PYTHON)
        sandbox.container_ref.remove_failures = [docker.errors.APIError("x")]
        assert manager.dispose(sandbox) is DisposalStatus.QUARANTINED
        sandbox.next_disposal_at = 0  # Skip the backoff.
        done = threading.Event()
        for _ in range(500):
            if sandbox.state is SandboxState.DISPOSED:
                done.set()
                break
            threading.Event().wait(0.01)
        assert done.is_set()
        assert pool.get_stats()["quarantined"] == 0
    finally:
        manager.shutdown()


def test_manager_closes_only_a_client_it_created(monkeypatch):
    client = FakeDocker()
    monkeypatch.setattr(docker, "from_env", lambda: client)
    manager = SandboxManager([pool_config()], max_sandboxes=2, owner=owner(), monitor_interval=60)
    manager.shutdown()
    client.close.assert_called_once()
