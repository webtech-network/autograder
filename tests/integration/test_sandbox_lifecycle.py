"""Real Docker sandbox ownership: leases, timeouts, cleanup, shutdown and dead-owner recovery.

Every manager here uses a per-test lease directory, so reclamation can only ever
select owners created by the test itself.
"""
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import docker
import pytest

from autograder import evaluate_submission
from autograder.models.dataclass.submission import Submission, SubmissionFile
from execution_host.docker import DockerHost, DockerSession
from sandbox_manager.api import create_app
from sandbox_manager.errors import Disposal, SandboxCapacityError, SandboxCleanupError, SandboxHandleError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig, SandboxRuntimeProfile
from sandbox_manager.models.sandbox_models import Language, ResponseCategory, SandboxState
from sandbox_manager.ownership import LABEL_OWNER, reclaim_dead_owners
from sandbox_manager.remote_client import RemoteSandboxContainer, RemoteSandboxManager
from tests.unit.sandbox.fakes import serve
from tests.unit.sandbox.test_remote_client import LossyAdapter, TrackingSession, lossy_factory

REPO = Path(__file__).resolve().parents[2]
TOKEN = "integration-control-token-0123456789"


@pytest.fixture(scope="module")
def client():
    instance = docker.from_env()
    yield instance
    instance.close()


def config(**overrides):
    values = dict(language=Language.PYTHON, pool_size=1, scale_limit=3, idle_timeout=300, running_timeout=60)
    values.update(overrides)
    return SandboxPoolConfig(**values)


def owned(client, owner_id):
    return client.containers.list(all=True, filters={"label": f"{LABEL_OWNER}={owner_id}"})


def gone(client, container_id):
    try:
        client.containers.get(container_id)
    except docker.errors.NotFound:
        return True
    return False


@pytest.fixture
def manager(tmp_path):
    instance = SandboxManager([config()], lease_dir=str(tmp_path)).start()
    yield instance
    instance.shutdown(raise_on_pending=False)


def test_lease_acquisition_preparation_use_and_disposal(manager, client):
    with DockerSession(manager, Language.PYTHON) as session:
        container = session.sandbox.container_ref
        container.reload()
        assert container.labels[LABEL_OWNER] == manager.owner_id
        assert all(mount["Type"] != "volume" for mount in container.attrs["Mounts"])  # nothing outlives it
        session.prepare_workdir({"main.py": SubmissionFile(
            "main.py", "open('output.txt', 'w').write('42')\nprint(input())")})
        result = session.run_commands(["hello"], program_command="python main.py", timeout=10)
        assert result.stdout.strip() == "hello" and result.category is ResponseCategory.SUCCESS
        assert session.read_artifact("output.txt").content_text == "42"
        with pytest.raises(FileNotFoundError):
            session.read_artifact("missing.txt")
    assert gone(client, container.id)
    assert session.sandbox.state is SandboxState.STOPPED
    session.close()  # repeated cleanup is a defined no-op
    assert manager.dispose(session.sandbox) is Disposal.ALREADY_DISPOSED
    stats = manager.get_pool_stats()["python"]
    assert stats["active"] == 0 and stats["cleanup_pending"] == 0 and stats["idle"] == 1


def test_timed_out_command_is_reported_and_its_sandbox_still_disposed(manager, client):
    session = DockerSession(manager, Language.PYTHON)
    started = time.monotonic()
    result = session.run_command("sleep 30", timeout=2)
    assert result.category is ResponseCategory.TIMEOUT and time.monotonic() - started < 10
    container_id = session.sandbox.container_ref.id
    started = time.monotonic()
    session.close()  # the exec is still running inside; disposal must not wait for it
    assert gone(client, container_id) and time.monotonic() - started < 15


def test_abandoned_lease_expires_and_is_destroyed(tmp_path, client):
    with SandboxManager([config(pool_size=0, running_timeout=2)], lease_dir=str(tmp_path),
                        monitor_interval=0.2) as manager:
        sandbox = manager.acquire(Language.PYTHON)
        deadline = time.monotonic() + 20
        while sandbox.state is not SandboxState.STOPPED and time.monotonic() < deadline:
            time.sleep(0.2)
        assert sandbox.state is SandboxState.STOPPED
        assert gone(client, sandbox.container_ref.id)
        assert manager.dispose(sandbox) is Disposal.ALREADY_DISPOSED


def test_docker_removal_failure_retains_the_container_record(manager, client):
    sandbox = manager.acquire(Language.PYTHON)
    real_remove = sandbox.container_ref.remove

    def failing_remove(**kwargs):
        raise docker.errors.APIError("injected removal failure")
    sandbox.container_ref.remove = failing_remove
    with pytest.raises(SandboxCleanupError):
        manager.dispose(sandbox)
    assert not gone(client, sandbox.container_ref.id)  # still exists and still tracked
    assert manager.get_pool_stats()["python"]["cleanup_pending"] == 1
    assert manager.cleanup_problems()[0]["attempts"] == 1
    sandbox.container_ref.remove = real_remove
    assert manager.dispose(sandbox) is Disposal.DISPOSED
    assert gone(client, sandbox.container_ref.id)


def test_shutdown_destroys_every_owned_container_and_releases_ownership(tmp_path, client):
    manager = SandboxManager([config(pool_size=2)], lease_dir=str(tmp_path)).start()
    manager.acquire(Language.PYTHON)  # a lease the host never closed
    assert len(owned(client, manager.owner_id)) == 2
    manager.shutdown()
    manager.shutdown()
    assert owned(client, manager.owner_id) == [] and not os.listdir(tmp_path)
    with pytest.raises(SandboxCapacityError):
        manager.acquire(Language.PYTHON)


def test_runc_profile_has_the_same_limits_and_a_working_workspace(tmp_path):
    profile = SandboxRuntimeProfile(runtime="runc")
    with SandboxManager([config(pool_size=0, profile=profile)], lease_dir=str(tmp_path)) as manager:
        with DockerSession(manager, Language.PYTHON) as session:
            container = session.sandbox.container_ref
            container.reload()
            host = container.attrs["HostConfig"]
            assert host["Runtime"] == "runc" and host["NetworkMode"] == "none"
            assert host["Memory"] == 128 * 1024 * 1024 and host["PidsLimit"] == 64
            assert host["Tmpfs"] == profile.container_options("runc")["tmpfs"]
            session.prepare_workdir({"run.sh": SubmissionFile("run.sh", "echo from-workspace")})
            result = session.run_command("sh -c 'cp run.sh x.sh && chmod +x x.sh && ./x.sh'", timeout=10)
            assert result.stdout.strip() == "from-workspace", result


OWNER_SCRIPT = textwrap.dedent("""
    import json, sys, time
    from sandbox_manager.manager import SandboxManager
    from sandbox_manager.models.pool_config import SandboxPoolConfig
    from sandbox_manager.models.sandbox_models import Language
    manager = SandboxManager([SandboxPoolConfig(Language.PYTHON, 1, 2, 300, 600)], lease_dir=sys.argv[1]).start()
    sandbox = manager.acquire(Language.PYTHON)
    manager.language_pools[Language.PYTHON].replenish()  # one leased, one warm
    print(json.dumps({"owner": manager.owner_id}), flush=True)
    time.sleep(600)
""")


def test_second_live_owner_never_reclaims_first_but_dead_owner_is_reclaimed(tmp_path, client):
    lease_dir = str(tmp_path)
    host_a = subprocess.Popen([sys.executable, "-c", OWNER_SCRIPT, lease_dir], cwd=REPO,
                              stdout=subprocess.PIPE, text=True)
    host_b = host_c = None
    try:
        owner_a = json.loads(host_a.stdout.readline())["owner"]
        a_containers = {c.id for c in owned(client, owner_a)}
        assert len(a_containers) == 2  # one leased, one warm

        host_b = SandboxManager([config()], lease_dir=lease_dir).start()
        assert owner_a in host_b.reclaim_report.live_owners
        assert {c.id for c in owned(client, owner_a)} == a_containers  # host A keeps running untouched
        b_containers = {c.id for c in owned(client, host_b.owner_id)}

        host_a.send_signal(signal.SIGKILL)  # no shutdown path runs
        host_a.wait(timeout=10)
        assert {c.id for c in owned(client, owner_a)} == a_containers  # leaked until a host proves death

        host_c = SandboxManager([config(pool_size=0)], lease_dir=lease_dir).start()
        assert set(host_c.reclaim_report.reclaimed) == a_containers
        assert owned(client, owner_a) == []
        assert {c.id for c in owned(client, host_b.owner_id)} == b_containers  # live B untouched
    finally:
        host_a.kill()
        host_a.wait()
        if host_c is None:  # the assertion path failed early: still reclaim the dead test owner
            reclaim_dead_owners(client, lease_dir)
        for host in (host_b, host_c):
            if host is not None:
                host.shutdown()
    assert not os.listdir(lease_dir)


@pytest.fixture
def remote_service(tmp_path, client):
    manager = SandboxManager([config(pool_size=0)], lease_dir=str(tmp_path))
    with serve(create_app(token=TOKEN, manager_factory=lambda: manager)) as url:
        yield url, manager
    assert owned(client, manager.owner_id) == []
    assert not os.listdir(tmp_path)  # service shutdown confirmed all cleanup


def test_remote_lease_over_real_http(remote_service, client):
    url, manager = remote_service
    TrackingSession.instances.clear()
    remote = RemoteSandboxManager(url, TOKEN, session_factory=TrackingSession)
    session = DockerSession(remote, Language.PYTHON)
    session.prepare_workdir({"main.py": SubmissionFile("main.py", "open('out.txt','w').write('ok')")})
    assert session.run_command("python main.py", timeout=10).exit_code == 0
    assert session.read_artifact("out.txt").content_text == "ok"
    with pytest.raises(FileNotFoundError):
        session.read_artifact("absent.txt")

    intruder = RemoteSandboxManager(url, TOKEN)._new_session("i" * 43)  # authenticated, wrong lease
    stolen = RemoteSandboxContainer(sandbox_id=session.sandbox.sandbox_id, language=Language.PYTHON,
                                    api_url=url, secret="i" * 43, session=intruder, lease_seconds=60)
    with pytest.raises(SandboxHandleError) as denied:
        stolen.extract_file("/app/out.txt")
    assert denied.value.code == "sandbox_not_found"
    with pytest.raises(SandboxHandleError):
        remote.dispose(stolen)

    [container] = owned(client, manager.owner_id)
    session.close()
    assert gone(client, container.id) and all(item.closed for item in TrackingSession.instances)
    with pytest.raises(SandboxHandleError) as expired:
        session.sandbox.run_command("id")
    assert expired.value.code == "sandbox_expired"


def test_remote_lost_delete_response_retry_confirms_destruction(remote_service, client):
    url, manager = remote_service
    adapter = LossyAdapter("DELETE", "", losses=1)
    remote = RemoteSandboxManager(url, TOKEN, session_factory=lossy_factory(adapter), retry_delay=0)
    sandbox = remote.acquire(Language.PYTHON)
    [container] = owned(client, manager.owner_id)
    assert remote.dispose(sandbox) is Disposal.DISPOSED
    assert adapter.sent == 2 and gone(client, container.id)


def test_remote_host_grades_and_service_shutdown_reclaims_abandoned_leases(remote_service, client):
    url, manager = remote_service
    definition = json.loads((REPO / "examples/contracts/input_output.json").read_text())
    host = DockerHost(mode="remote", api_url=url, api_token=TOKEN)
    try:
        outcome = evaluate_submission(Submission(
            "student", 1, 1, {"main.py": SubmissionFile("main.py", "print(input())")}, language=Language.PYTHON),
            definition=definition, capabilities=host.capabilities)
        assert outcome.status == "completed" and outcome.score == 100
    finally:
        host.close()
    # A client that crashed mid-lease: the service shutdown (fixture exit) must destroy it.
    RemoteSandboxManager(url, TOKEN).acquire(Language.PYTHON)
    assert len(owned(client, manager.owner_id)) == 1
