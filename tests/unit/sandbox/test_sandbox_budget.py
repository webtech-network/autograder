"""The host-wide sandbox budget: waiting, concurrent creation, shutdown and accounting.

Docker is the in-memory fake; creation is held open with events and barriers so
every interleaving below is forced, never left to timing.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import docker
import pytest

from autograder.models.abstract.execution_test import RUN_TIMEOUT_SECONDS
from autograder.models.capabilities import ExecutionBudget
from autograder.models.language import Language
from sandbox_manager.errors import SandboxCapacityTimeout
from sandbox_manager.language_pool import SandboxUnavailableError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import DEFAULT_RUNNING_TIMEOUT, MIN_RUNNING_TIMEOUT, SandboxHostConfig
from sandbox_manager.models.sandbox_models import DisposalStatus, SandboxState
from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config

PY, JAVA = Language.PYTHON, Language.JAVA
LONG_WAIT = 30.0  # Only ever reached if the behaviour under test is broken.


def make_manager(client, max_sandboxes, languages=(PY,), pool_size=0):
    return SandboxManager([pool_config(language, pool_size=pool_size) for language in languages], client,
                          max_sandboxes=max_sandboxes, owner=owner(), reclaim_orphans=False, monitor_interval=3600)


def wait_until(manager, predicate):
    """Block on the budget's own condition (notified on every slot change) until ``predicate``."""
    with manager.budget.condition:
        assert manager.budget.condition.wait_for(predicate, timeout=LONG_WAIT)


def waiting(manager, count):
    return lambda: len(manager.budget._waiters) == count  # pylint: disable=protected-access


def slot_holders(manager):
    """creating + active + closing + quarantined across every pool (call with the lock held)."""
    return sum(pool._creating + len(pool.active_sandboxes) + len(pool.closing_sandboxes)  # pylint: disable=protected-access
               + len(pool.quarantined_sandboxes) for pool in manager.language_pools.values())


@pytest.fixture
def client():
    return FakeDocker()


# ------------------------------------------------------------------ waiting

def test_saturation_waits_and_wakes_on_dispose(client):
    manager = make_manager(client, 1)
    try:
        held = manager.get_sandbox(PY)
        with ThreadPoolExecutor(1) as executor:
            pending = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 1))
            assert not pending.done()
            assert manager.dispose(held) is DisposalStatus.DISPOSED
            granted = pending.result(timeout=LONG_WAIT)
        assert granted.state is SandboxState.ACTIVE
        assert manager.get_budget_stats() == {"max_sandboxes": 1, "held": 1, "waiting": 0}
    finally:
        manager.shutdown()


def test_wait_expiry_raises_capacity_timeout_and_leaves_no_trace(client):
    manager = make_manager(client, 1)
    try:
        manager.get_sandbox(PY)
        with pytest.raises(SandboxCapacityTimeout):
            manager.get_sandbox(PY)                      # wait_seconds=0: no waiting at all.
        with pytest.raises(SandboxCapacityTimeout, match="max_sandboxes: 1"):
            manager.get_sandbox(PY, wait_seconds=0.05)   # Expires; nothing frees a slot.
        assert manager.get_budget_stats() == {"max_sandboxes": 1, "held": 1, "waiting": 0}
        assert len(client.live) == 1
    finally:
        manager.shutdown()


def test_waiters_are_served_in_arrival_order_across_languages(client):
    manager = make_manager(client, 1, languages=(PY, JAVA))
    try:
        first = manager.get_sandbox(PY)
        with ThreadPoolExecutor(2) as executor:
            java = executor.submit(manager.get_sandbox, JAVA, LONG_WAIT)
            wait_until(manager, waiting(manager, 1))
            python = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 2))
            manager.dispose(first)
            granted = java.result(timeout=LONG_WAIT)     # One budget for every language, FIFO.
            assert granted.language is JAVA and not python.done()
            manager.dispose(granted)
            assert python.result(timeout=LONG_WAIT).language is PY
    finally:
        manager.shutdown()


def test_quarantined_container_keeps_its_slot_until_removal_is_confirmed(client):
    manager = make_manager(client, 1)
    try:
        sandbox = manager.get_sandbox(PY)
        sandbox.container_ref.remove_failures = [docker.errors.APIError("busy")]
        assert manager.dispose(sandbox) is DisposalStatus.QUARANTINED
        with pytest.raises(SandboxCapacityTimeout):
            manager.get_sandbox(PY)
        with ThreadPoolExecutor(1) as executor:
            pending = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 1))
            assert manager.language_pools[PY].retry_quarantined(final=True) == [DisposalStatus.DISPOSED]
            assert pending.result(timeout=LONG_WAIT).state is SandboxState.ACTIVE
    finally:
        manager.shutdown()


# ------------------------------------------------------------------ creation outside the lock

def test_concurrent_cold_acquisitions_create_in_parallel(client):
    """N creations are inside Docker at once; a serialized pool would break the barrier."""
    inside = threading.Barrier(4, timeout=LONG_WAIT)
    client.on_run = lambda _kwargs: inside.wait()
    manager = make_manager(client, 4)
    try:
        with ThreadPoolExecutor(4) as executor:
            sandboxes = list(executor.map(lambda _: manager.get_sandbox(PY), range(4)))
        assert len({sandbox.container_ref.name for sandbox in sandboxes}) == 4
        assert manager.get_pool_stats()["python"]["active"] == 4
    finally:
        manager.shutdown()


def test_budget_is_never_exceeded_under_contention(client):
    limit, jobs = 3, 24
    manager = make_manager(client, limit, languages=(PY, JAVA))
    samples = []

    def observe(_kwargs=None):
        with manager.budget.condition:
            samples.append(slot_holders(manager))
            assert manager.budget.held <= limit

    client.on_run = observe
    lock = threading.Lock()
    created = []
    # The first `limit` holders keep their slots until every other job is queued.
    saturated = threading.Barrier(limit, timeout=LONG_WAIT,
                                  action=lambda: wait_until(manager, waiting(manager, jobs - limit)))

    def job(index):
        sandbox = manager.get_sandbox(PY if index % 2 else JAVA, wait_seconds=LONG_WAIT)
        observe()
        with lock:
            created.append(sandbox)
            first = len(created) <= limit
        if first:
            saturated.wait()
        sandbox.container_ref.remove = wrap_remove(sandbox.container_ref.remove, observe)
        assert manager.dispose(sandbox) is DisposalStatus.DISPOSED

    try:
        with ThreadPoolExecutor(jobs) as executor:
            list(executor.map(job, range(jobs)))
        assert len(created) == jobs                       # Every acquisition completed; none failed.
        assert max(samples) == limit and all(holders <= limit for holders in samples)
        assert manager.get_budget_stats() == {"max_sandboxes": limit, "held": 0, "waiting": 0}
        assert client.live == {}
    finally:
        manager.shutdown()


def wrap_remove(remove, observe):
    def removing(**kwargs):
        observe()                                         # Closing still counts while Docker removes it.
        return remove(**kwargs)
    return removing


def test_failed_creation_releases_its_slot_to_the_next_waiter(client):
    manager = make_manager(client, 1)
    try:
        held = manager.get_sandbox(PY)
        failing = threading.Event()

        def run(_kwargs):
            if failing.is_set():
                failing.clear()
                raise docker.errors.APIError("image pull failed")

        client.on_run = run
        with ThreadPoolExecutor(2) as executor:
            doomed = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 1))
            survivor = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 2))
            failing.set()
            manager.dispose(held)
            with pytest.raises(SandboxUnavailableError):
                doomed.result(timeout=LONG_WAIT)
            assert survivor.result(timeout=LONG_WAIT).state is SandboxState.ACTIVE
        assert manager.get_budget_stats()["held"] == 1
        assert manager.get_pool_stats()["python"]["creating"] == 0
    finally:
        manager.shutdown()


def test_concurrent_gvisor_fallback_creates_each_container_once(client):
    """Several creators discover the missing runtime at once; each falls back for its own name only."""
    attempts = threading.Barrier(3, timeout=LONG_WAIT)

    def run(kwargs):
        if kwargs.get("runtime") == "runsc":
            attempts.wait()                               # All three try gVisor before any learns it is absent.

    client.on_run = run
    manager = make_manager(client, 3)
    try:
        with ThreadPoolExecutor(3) as executor:
            sandboxes = list(executor.map(lambda _: manager.get_sandbox(PY), range(3)))
        names = sorted(sandbox.container_ref.name for sandbox in sandboxes)
        assert len(set(names)) == 3 and sorted(container.name for container in client.live.values()) == names
        assert all("runtime" not in sandbox.container_ref.kwargs for sandbox in sandboxes)
        client.on_run = None
        manager.dispose(sandboxes[0])
        manager.get_sandbox(PY)
        assert "runtime" not in client.containers.run_calls[-1]  # The fallback is remembered.
        assert len(client.containers.run_calls) == 7
    finally:
        manager.shutdown()


# ------------------------------------------------------------------ warm pool

def test_warm_containers_are_outside_the_budget_but_taking_one_takes_a_slot(client):
    manager = make_manager(client, 1, languages=(PY, JAVA), pool_size=1)
    try:
        stats = manager.get_pool_stats()
        assert stats["python"]["idle"] == stats["java"]["idle"] == 1
        assert manager.get_budget_stats()["held"] == 0
        warm = manager.get_sandbox(PY)
        assert manager.get_budget_stats()["held"] == 1 and len(client.live) == 2  # Nothing new created.
        with pytest.raises(SandboxCapacityTimeout):
            manager.get_sandbox(JAVA)                     # A warm Java container exists, but no slot.
        manager.dispose(warm)
        assert manager.get_sandbox(JAVA).language is JAVA
    finally:
        manager.shutdown()


def test_warm_up_never_takes_a_slot_an_acquisition_is_waiting_for(client):
    manager = make_manager(client, 1, pool_size=1)
    pool = manager.language_pools[PY]
    try:
        held = manager.get_sandbox(PY)                    # Took the only warm container.
        with ThreadPoolExecutor(1) as executor:
            pending = executor.submit(manager.get_sandbox, PY, LONG_WAIT)
            wait_until(manager, waiting(manager, 1))
            pool.replenish()                              # Budget full and a waiter: no warm-up.
            assert pool.get_stats()["idle"] == 0
            manager.dispose(held)
            pending.result(timeout=LONG_WAIT)
    finally:
        manager.shutdown()


# ------------------------------------------------------------------ shutdown

def test_shutdown_fails_waiters_and_removes_everything(client):
    manager = make_manager(client, 1, languages=(PY, JAVA))
    manager.get_sandbox(PY)
    with ThreadPoolExecutor(2) as executor:
        waiters = [executor.submit(manager.get_sandbox, language, LONG_WAIT) for language in (PY, JAVA)]
        wait_until(manager, waiting(manager, 2))
        manager.shutdown()
        for pending in waiters:
            with pytest.raises(SandboxUnavailableError):
                pending.result(timeout=LONG_WAIT)
    assert client.live == {}
    assert manager.get_budget_stats() == {"max_sandboxes": 1, "held": 0, "waiting": 0}


def test_shutdown_during_creation_removes_the_new_container_before_returning(client):
    creating = threading.Event()
    release = threading.Event()

    def run(_kwargs):
        creating.set()
        assert release.wait(LONG_WAIT)

    client.on_run = run
    manager = make_manager(client, 2)
    pool = manager.language_pools[PY]
    with ThreadPoolExecutor(2) as executor:
        acquisition = executor.submit(manager.get_sandbox, PY)
        assert creating.wait(LONG_WAIT)
        stopping = executor.submit(manager.shutdown)
        wait_until(manager, lambda: pool._closed)        # pylint: disable=protected-access
        assert not stopping.done()                        # Shutdown waits for the in-flight creation.
        release.set()
        stopping.result(timeout=LONG_WAIT)
        with pytest.raises(SandboxUnavailableError):
            acquisition.result(timeout=LONG_WAIT)
    assert client.live == {}
    assert pool.get_stats()["creating"] == 0 and manager.get_budget_stats()["held"] == 0


# ------------------------------------------------------------------ configuration

def write(tmp_path, general):
    path = tmp_path / "sandbox.yml"
    path.write_text(f"general:\n{general}runtimes:\n  python: sandbox-py:latest\n  java: sandbox-java:latest\n")
    return str(path)


def test_configuration_is_the_budget_plus_warm_pool_size(tmp_path):
    config = SandboxHostConfig.load_from_yaml(write(tmp_path, "  max_sandboxes: 8\n  pool_size: 1\n"))
    assert config.max_sandboxes == 8
    assert [(pool.language, pool.pool_size) for pool in config.pools] == [(PY, 1), (JAVA, 1)]


@pytest.mark.parametrize("general,message", [
    ("  pool_size: 1\n", "max_sandboxes .*is required"),
    ("  max_sandboxes: 0\n", "max_sandboxes must be an integer >= 1"),
    ("  max_sandboxes: two\n", "max_sandboxes must be an integer"),
    ("  max_sandboxes: 2\n  pool_size: 3\n", "pool_size \\(3\\) cannot exceed max_sandboxes \\(2\\)"),
    ("  max_sandboxes: 2\n  scale_limit: 3\n", "replaced by the host-wide general.max_sandboxes"),
    ("  max_sandboxes: 2\n  idle_timeout: 300\n", "idle_timeout was removed"),
    ("  max_sandboxes: 2\n  pool_sise: 1\n", "unknown setting general.pool_sise"),
    # The old default: every execution definition would need longer than the host grants.
    ("  max_sandboxes: 2\n  running_timeout: 60\n", "running_timeout must be an integer >= 92 \\(the smallest"),
    ("  max_sandboxes: 2\n  running_timeout: 91\n", "running_timeout must be an integer >= 92"),
    ("  max_sandboxes: 2\n  running_timeout: 900.5\n", "running_timeout must be an integer >= 92"),
])
def test_unworkable_or_removed_settings_are_rejected_at_startup(tmp_path, general, message):
    with pytest.raises(ValueError, match=message):
        SandboxHostConfig.load_from_yaml(write(tmp_path, general))


def test_running_timeout_defaults_to_the_shipped_maximum_and_admits_the_smallest_session(tmp_path):
    omitted = SandboxHostConfig.load_from_yaml(write(tmp_path, "  max_sandboxes: 2\n"))
    assert omitted.running_timeout == DEFAULT_RUNNING_TIMEOUT == 900
    smallest = ExecutionBudget(RUN_TIMEOUT_SECONDS, 1).session_seconds  # one I/O criterion: 30 + 2 + 60
    assert MIN_RUNNING_TIMEOUT == smallest == 92
    config = SandboxHostConfig.load_from_yaml(write(tmp_path, "  max_sandboxes: 2\n  running_timeout: 92\n"))
    assert config.running_timeout == 92


def test_manager_rejects_an_empty_budget(client):
    with pytest.raises(ValueError, match="at least one"):
        make_manager(client, 0)
