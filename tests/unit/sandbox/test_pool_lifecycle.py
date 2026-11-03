"""Local pool ownership with a mocked Docker client: no record is forgotten before removal."""
import os
import signal
from itertools import count
from unittest.mock import MagicMock

import docker
import pytest

from sandbox_manager.errors import Disposal, SandboxCapacityError, SandboxCleanupError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig, SandboxRuntimeProfile
from sandbox_manager.models.sandbox_models import Language, SandboxState
from sandbox_manager.ownership import LABEL_OWNER


class FakeDocker:
    """Minimal docker client: tracks created containers and can fail removal."""

    def __init__(self, runtimes=("runc",)):
        self.runtimes = runtimes
        self.created = []
        self.remove_failures = 0
        self._ids = count(1)

    def info(self):
        return {"Runtimes": {name: {} for name in self.runtimes}}

    @property
    def containers(self):
        return self

    def run(self, image, name, labels, **options):
        container = MagicMock(name=name)
        container.id = f"{next(self._ids):064x}"
        container.labels = labels
        container.options = options
        container.removed = False

        def remove(force=False, v=False):
            if self.remove_failures:
                self.remove_failures -= 1
                raise docker.errors.APIError("daemon busy")
            container.removed = True
        container.remove.side_effect = remove
        self.created.append(container)
        return container

    def list(self, all=False, filters=None):  # pylint: disable=redefined-builtin
        key, _, value = filters["label"].partition("=")
        return [c for c in self.created if not c.removed and c.labels.get(key) == value]

    def get(self, name):
        raise docker.errors.NotFound("absent")

    def close(self):
        pass


def config(**overrides):
    values = dict(language=Language.PYTHON, pool_size=0, scale_limit=2, idle_timeout=300, running_timeout=60)
    values.update(overrides)
    return SandboxPoolConfig(**values)


@pytest.fixture
def docker_client():
    return FakeDocker()


@pytest.fixture
def manager(docker_client, tmp_path):
    instance = SandboxManager([config()], client=docker_client, lease_dir=str(tmp_path)).start(monitor=False)
    yield instance
    docker_client.remove_failures = 0
    instance.shutdown(raise_on_pending=False)


def test_dispose_is_confirmed_and_repeatable(manager, docker_client):
    sandbox = manager.acquire(Language.PYTHON)
    assert manager.dispose(sandbox) is Disposal.DISPOSED
    assert sandbox.state is SandboxState.STOPPED
    sandbox.container_ref.remove.assert_called_once_with(force=True, v=True)
    assert manager.dispose(sandbox) is Disposal.ALREADY_DISPOSED
    assert sandbox.container_ref.remove.call_count == 1
    assert manager.get_pool_stats()["python"]["total"] == 0


def test_removal_failure_retains_the_record_until_a_retry_confirms_it(manager, docker_client):
    pool = manager.language_pools[Language.PYTHON]
    sandbox = manager.acquire(Language.PYTHON)
    docker_client.remove_failures = 1
    with pytest.raises(SandboxCleanupError):
        manager.dispose(sandbox)
    # The only ownership record still exists and is observable.
    assert sandbox in pool.closing and sandbox.state is SandboxState.CLOSING
    assert manager.get_pool_stats()["python"]["cleanup_pending"] == 1
    [problem] = manager.cleanup_problems()
    assert problem["attempts"] == 1 and "daemon busy" in problem["last_error"]
    pool.retry_cleanup()  # backoff not yet elapsed: no attempt
    assert sandbox.container_ref.remove.call_count == 1
    pool.closing[sandbox].next_attempt = 0
    pool.retry_cleanup()
    assert sandbox.state is SandboxState.STOPPED and not pool.closing
    assert manager.dispose(sandbox) is Disposal.ALREADY_DISPOSED


def test_repeated_dispose_retries_a_retained_record_immediately(manager, docker_client):
    sandbox = manager.acquire(Language.PYTHON)
    docker_client.remove_failures = 2
    for _ in range(2):
        with pytest.raises(SandboxCleanupError):
            manager.dispose(sandbox)
    assert manager.dispose(sandbox) is Disposal.DISPOSED


def test_unconfirmed_cleanup_holds_capacity(manager, docker_client):
    first, second = manager.acquire(Language.PYTHON), manager.acquire(Language.PYTHON)
    docker_client.remove_failures = 1
    with pytest.raises(SandboxCleanupError):
        manager.dispose(first)
    with pytest.raises(SandboxCapacityError):
        manager.acquire(Language.PYTHON)
    manager.dispose(first)
    manager.dispose(second)
    assert manager.acquire(Language.PYTHON)


def test_missing_container_counts_as_confirmed(manager):
    sandbox = manager.acquire(Language.PYTHON)
    sandbox.container_ref.remove.side_effect = docker.errors.NotFound("gone")
    assert manager.dispose(sandbox) is Disposal.DISPOSED


def test_expired_lease_is_disposed_and_later_close_is_defined(manager):
    pool = manager.language_pools[Language.PYTHON]
    sandbox = manager.acquire(Language.PYTHON)
    sandbox.last_updated = sandbox.last_updated.replace(year=2000)
    pool.expire_leases()
    assert sandbox.state is SandboxState.STOPPED
    assert manager.dispose(sandbox) is Disposal.ALREADY_DISPOSED


def test_foreign_sandbox_is_rejected(manager, docker_client, tmp_path):
    other = SandboxManager([config()], client=docker_client, lease_dir=str(tmp_path)).start(monitor=False)
    try:
        foreign = other.acquire(Language.PYTHON)
        with pytest.raises(ValueError):
            manager.dispose(foreign)
        assert other.dispose(foreign) is Disposal.DISPOSED
    finally:
        other.shutdown()


def test_shutdown_keeps_the_lease_file_until_cleanup_is_confirmed(docker_client, tmp_path):
    manager = SandboxManager([config(pool_size=1)], client=docker_client, lease_dir=str(tmp_path)).start(monitor=False)
    lease_file = manager.owner.path
    manager.acquire(Language.PYTHON)
    docker_client.remove_failures = 10
    with pytest.raises(SandboxCleanupError):
        manager.shutdown()
    assert os.path.exists(lease_file) and not manager.owner.held
    with pytest.raises(SandboxCapacityError):
        manager.acquire(Language.PYTHON)
    docker_client.remove_failures = 0
    # A later host start proves the owner dead and reclaims what shutdown could not remove.
    successor = SandboxManager([config()], client=docker_client, lease_dir=str(tmp_path)).start(monitor=False)
    assert len(successor.reclaim_report.reclaimed) == 1
    assert not os.path.exists(lease_file)
    successor.shutdown()
    assert not os.listdir(tmp_path)


def test_clean_shutdown_is_repeatable_and_sweeps_untracked_containers(docker_client, tmp_path):
    manager = SandboxManager([config(pool_size=1)], client=docker_client, lease_dir=str(tmp_path)).start(monitor=False)
    stray = docker_client.run("img", "stray", {LABEL_OWNER: manager.owner_id})  # e.g. created but never started
    manager.shutdown()
    manager.shutdown()
    assert stray.removed and all(container.removed for container in docker_client.created)
    assert not os.path.exists(manager.owner.path)


def test_runtime_policy_is_resolved_once_with_identical_limits(tmp_path):
    profile = SandboxRuntimeProfile()
    runsc, runc = profile.container_options("runsc"), profile.container_options("runc")
    assert {k: v for k, v in runsc.items() if k != "runtime"} == {k: v for k, v in runc.items() if k != "runtime"}
    assert ",exec," in runc["tmpfs"]["/app"] and runc["network_mode"] == "none"
    assert profile.resolve_runtime({"runc", "runsc"}) == "runsc"
    assert profile.resolve_runtime({"runc"}) == "runc"
    with pytest.raises(RuntimeError):
        SandboxRuntimeProfile(runtime="runsc").resolve_runtime({"runc"})
    with pytest.raises(ValueError):
        SandboxRuntimeProfile.from_mapping({"network": "bridge"})

    client = FakeDocker(runtimes=("runc", "runsc"))
    with SandboxManager([config(pool_size=1)], client=client, lease_dir=str(tmp_path)) as manager:
        assert manager.language_pools[Language.PYTHON].runtime == "runsc"
    created = client.created[0]
    assert created.options == runsc and created.labels[LABEL_OWNER] == manager.owner_id


def test_failed_start_releases_ownership(tmp_path):
    client = FakeDocker(runtimes=("runc",))
    manager = SandboxManager([config(profile=SandboxRuntimeProfile(runtime="runsc"))], client=client,
                             lease_dir=str(tmp_path))
    with pytest.raises(RuntimeError, match="runsc"):
        manager.start()
    assert not manager.owner.held and not os.listdir(tmp_path)


def test_library_installs_no_signal_handlers(docker_client, tmp_path):
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    with SandboxManager([config()], client=docker_client, lease_dir=str(tmp_path)):
        assert {sig: signal.getsignal(sig) for sig in before} == before
    import sandbox_manager.manager as module
    source = open(module.__file__, encoding="utf-8").read()
    assert "signal.signal(" not in source and "atexit.register(" not in source


def test_cleanup_failure_keeps_the_grade_and_the_pool_record(manager, docker_client):
    from autograder import evaluate_submission
    from autograder.models.capabilities import HostCapabilities
    from execution_host.docker import DockerSession
    from tests.unit.pipeline.test_host_capabilities import definition, submission

    sessions = []

    def execution(language):
        session = DockerSession(manager, language)
        session.sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0, output=(b"ok", b""))
        sessions.append(session)
        return session

    docker_client.remove_failures = 1
    events = []
    outcome = evaluate_submission(submission(), definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "prepare", "command": "true"}]}}}),
        capabilities=HostCapabilities(execution=execution), observer=events.append)
    assert outcome.status == "completed" and outcome.score == 100
    assert events[-1].operation == "close_session" and events[-1].error.code == "CLEANUP_ERROR"
    [session] = sessions
    pool = manager.language_pools[Language.PYTHON]
    assert session.sandbox in pool.closing  # the host still owns and retries it
    session.close()  # a later close retries and confirms
    assert session.sandbox.state is SandboxState.STOPPED and not pool.closing
    session.close()
