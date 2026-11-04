"""Real-Docker lifecycle checks: owner leases, disposal, quarantine and shutdown.

Every test filters containers by its own owner id, so concurrent test runs and
production sandboxes on the same daemon are never counted or removed.
"""
import re
import time
from unittest.mock import patch

import docker
import pytest

from sandbox_manager.language_pool import LABEL_LANGUAGE, LABEL_POOL_ID
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import DisposalStatus, Language, SandboxState
from sandbox_manager.ownership import (
    APP_LABEL_VALUE,
    LABEL_APP,
    LABEL_OWNER,
    LABEL_OWNER_HOST,
    LABEL_OWNER_PROCESS,
    OwnerIdentity,
    reclaim_selected,
)


def config(pool_size=0, scale_limit=2, running_timeout=60, disposal_attempts=3):
    return SandboxPoolConfig(language=Language.PYTHON, pool_size=pool_size, scale_limit=scale_limit,
                             idle_timeout=300, running_timeout=running_timeout,
                             disposal_attempts=disposal_attempts)


@pytest.fixture(scope="module")
def client():
    try:
        value = docker.from_env()
        value.images.get(Language.PYTHON.image)
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"Docker or {Language.PYTHON.image} unavailable: {exc}")
    yield value
    value.close()


def owned(client, owner_id):
    return client.containers.list(all=True, filters={"label": [f"{LABEL_APP}={APP_LABEL_VALUE}",
                                                               f"{LABEL_OWNER}={owner_id}"]})


def wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


def fabricated_container(client, labels, name_suffix):
    """A cheap labelled container standing in for another owner's sandbox."""
    return client.containers.run(Language.PYTHON.image, command="sleep infinity", detach=True,
                                 network_mode="none", labels=labels,
                                 name=f"ag-test-{name_suffix}-{OwnerIdentity.current().owner_id[:8]}")


def test_acquire_run_dispose_removes_container_and_is_idempotent(client):
    with SandboxManager([config()], client) as manager:
        sandbox = manager.get_sandbox(Language.PYTHON)
        assert sandbox.state is SandboxState.ACTIVE
        result = sandbox.run_command("python -c 'print(2+2)'")
        assert result.exit_code == 0 and "4" in result.stdout
        sandbox.container_ref.reload()
        labels = sandbox.container_ref.labels
        assert labels[LABEL_APP] == APP_LABEL_VALUE
        assert labels[LABEL_OWNER] == manager.owner.owner_id
        assert labels[LABEL_OWNER_PROCESS] == manager.owner.process_token
        assert labels[LABEL_LANGUAGE] == "python" and LABEL_POOL_ID in labels
        assert re.match(r'^ag-sbx-python-[a-f0-9]{8}-\d{4}$', sandbox.container_ref.name)

        assert manager.dispose(sandbox) is DisposalStatus.DISPOSED
        assert manager.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
        assert sandbox.state is SandboxState.DISPOSED
        assert owned(client, manager.owner.owner_id) == []
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(sandbox.container_ref.id)


def test_workspace_is_a_bounded_writable_tmpfs_under_the_active_runtime(client):
    with SandboxManager([config()], client) as manager:
        with manager.acquire_sandbox(Language.PYTHON) as sandbox:
            from autograder.models.dataclass.submission import SubmissionFile
            sandbox.prepare_workdir({"pkg/main.py": SubmissionFile("pkg/main.py", "print('hi')")})
            assert sandbox.run_command("python3 pkg/main.py").stdout.strip() == "hi"
            mounts = sandbox.run_command("cat /proc/mounts").stdout
            assert re.search(r"^\S+ /app tmpfs ", mounts, re.M), mounts
            assert re.search(r"^\S+ /tmp tmpfs \S*noexec", mounts, re.M), mounts
            sandbox.container_ref.reload()
            # No anonymous /app volume is left behind on removal.
            assert not [m for m in sandbox.container_ref.attrs["Mounts"] if m.get("Destination") == "/app"]


def test_disposal_failure_quarantines_then_monitor_retry_confirms_removal(client):
    with SandboxManager([config(scale_limit=1)], client, monitor_interval=0.2) as manager:
        pool = manager.language_pools[Language.PYTHON]
        sandbox = manager.get_sandbox(Language.PYTHON)
        container_id = sandbox.container_ref.id
        real_remove = sandbox.container_ref.remove
        calls = []

        def flaky_remove(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise docker.errors.APIError("simulated daemon failure")
            return real_remove(**kwargs)

        with patch.object(sandbox.container_ref, "remove", side_effect=flaky_remove):
            assert manager.dispose(sandbox) is DisposalStatus.QUARANTINED
            # Still tracked and counted: capacity is not silently over-committed.
            assert client.containers.get(container_id).status == "running"
            stats = manager.get_pool_stats()["python"]
            assert stats["quarantined"] == 1 and stats["total"] == 1
            with pytest.raises(ValueError):
                manager.get_sandbox(Language.PYTHON)
            assert manager.dispose(sandbox) is DisposalStatus.QUARANTINED
            assert wait_until(lambda: sandbox.state is SandboxState.DISPOSED)
        assert len(calls) == 2
        assert calls[0] == {"force": True, "v": True}
        assert pool.get_stats()["quarantined"] == 0
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(container_id)


def test_running_timeout_disposes_through_the_same_path(client):
    with SandboxManager([config(running_timeout=1)], client, monitor_interval=0.2) as manager:
        sandbox = manager.get_sandbox(Language.PYTHON)
        assert wait_until(lambda: sandbox.state is SandboxState.DISPOSED)
        assert manager.dispose(sandbox) is DisposalStatus.ALREADY_DISPOSED
        assert owned(client, manager.owner.owner_id) == []


def test_shutdown_disposes_everything_and_stops_monitor(client):
    manager = SandboxManager([config(pool_size=1, scale_limit=3)], client)
    try:
        active = manager.get_sandbox(Language.PYTHON)
        assert wait_until(lambda: len(owned(client, manager.owner.owner_id)) == 2)
    finally:
        manager.shutdown()
    assert not manager.monitor_thread.is_alive()
    assert owned(client, manager.owner.owner_id) == []
    assert manager.dispose(active) is DisposalStatus.ALREADY_DISPOSED
    manager.shutdown()  # Idempotent.


def test_shutdown_with_failing_container_reports_it_and_keeps_owner_labels(client):
    manager = SandboxManager([config()], client)
    sandbox = manager.get_sandbox(Language.PYTHON)
    container_id = sandbox.container_ref.id
    try:
        with patch.object(sandbox.container_ref, "remove", side_effect=docker.errors.APIError("stuck")):
            manager.shutdown()
        assert sandbox.state is SandboxState.QUARANTINED
        assert manager.get_pool_stats()["python"]["quarantined"] == 1
        # The surviving container still names its (now finished) owner lease.
        assert client.containers.get(container_id).labels[LABEL_OWNER] == manager.owner.owner_id
    finally:
        client.containers.get(container_id).remove(force=True, v=True)


def test_two_live_owners_never_reclaim_each_other(client):
    first = SandboxManager([config(pool_size=1)], client)
    second = None
    try:
        assert wait_until(lambda: len(owned(client, first.owner.owner_id)) == 1)
        second = SandboxManager([config(pool_size=1)], client)  # Startup reclamation runs here.
        assert wait_until(lambda: len(owned(client, second.owner.owner_id)) == 1)
        assert len(owned(client, first.owner.owner_id)) == 1
        with first.acquire_sandbox(Language.PYTHON) as sandbox:
            assert sandbox.run_command("echo alive").stdout.strip() == "alive"
        # Explicit operator reclamation also refuses a live local owner.
        assert reclaim_selected(client, owner=second.owner.owner_id) == []
        assert len(owned(client, second.owner.owner_id)) >= 1
    finally:
        first.shutdown()
        if second is not None:
            second.shutdown()


def test_dead_local_owner_is_reclaimed_but_remote_and_legacy_owners_are_not(client):
    me = OwnerIdentity.current()
    dead = {LABEL_APP: APP_LABEL_VALUE, LABEL_OWNER: "dead-owner-" + me.owner_id[:8],
            LABEL_OWNER_HOST: me.hostname,
            # pid above the kernel maximum (2**22) can never be running.
            LABEL_OWNER_PROCESS: f"{me.boot_id}:{2 ** 22 + 1}:12345"}
    rebooted = dict(dead, **{LABEL_OWNER: "rebooted-" + me.owner_id[:8],
                             LABEL_OWNER_PROCESS: f"previous-boot:{me.pid}:{me.start_ticks}"})
    remote = dict(dead, **{LABEL_OWNER: "remote-" + me.owner_id[:8], LABEL_OWNER_HOST: "another-host"})
    legacy = {LABEL_APP: APP_LABEL_VALUE, "autograder.test.legacy": me.owner_id}
    containers = {name: fabricated_container(client, labels, name) for name, labels in
                  [("dead", dead), ("rebooted", rebooted), ("remote", remote), ("legacy", legacy)]}
    manager = None
    try:
        manager = SandboxManager([config()], client)
        survivors = {name for name, container in containers.items() if _exists(client, container.id)}
        assert survivors == {"remote", "legacy"}
        # The operator command handles the cases automatic reclamation cannot prove.
        rows = reclaim_selected(client, dead_host="another-host")
        assert [row["owner"] for row in rows] == [remote[LABEL_OWNER]]
        assert not _exists(client, containers["remote"].id)
        legacy_rows = reclaim_selected(client, legacy=True, dry_run=True)
        assert containers["legacy"].id in {row["id"] for row in legacy_rows}
        assert _exists(client, containers["legacy"].id)
    finally:
        if manager is not None:
            manager.shutdown()
        for container in containers.values():
            if _exists(client, container.id):
                client.containers.get(container.id).remove(force=True)


def _exists(client, container_id):
    try:
        client.containers.get(container_id)
        return True
    except docker.errors.NotFound:
        return False
