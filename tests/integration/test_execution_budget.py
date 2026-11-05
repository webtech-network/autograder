"""One execution time budget, granted by the host and enforced by the sandbox (COR-02).

Every test runs under each runtime this daemon offers: gVisor (``runsc``) when it
is installed, and Docker's default runtime (``runc``), forced. The definitions use
the built-in 30 s process deadline and the shipped ``sandbox_config.yml``.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import docker
import pytest
import requests

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.language import Language
from autograder.models.process import ProcessRequest
from execution_host.docker import docker_capabilities
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxHostConfig
from sandbox_manager.ownership import APP_FILTER, LABEL_OWNER, LABEL_OWNER_PROCESS
from sandbox_manager.remote_client import RemoteSandboxManager
from tests.integration import lifetime_owner

ROOT = Path(__file__).resolve().parents[2]

PROGRAMS = {
    "loop.py": "while True:\n    pass\n",
    # Correct, and slow: most of the 30 s process deadline.
    "slow.py": "import time\ntime.sleep(25)\nprint('ok')\n",
}


def _daemon_runtimes():
    client = docker.from_env()
    try:
        offered = client.info().get("Runtimes", {})
    finally:
        client.close()
    return [runtime for runtime in ("runsc", "runc") if runtime == "runc" or runtime in offered]


@pytest.fixture(scope="module", params=_daemon_runtimes())
def runtime(request):
    return request.param


@pytest.fixture(scope="module")
def manager(runtime):
    """The shipped host configuration, Python only, on the runtime under test."""
    config = SandboxHostConfig.load_from_yaml("sandbox_config.yml")
    pools = [pool for pool in config.pools if pool.language is Language.PYTHON]
    manager = SandboxManager(pools, max_sandboxes=config.max_sandboxes)
    if runtime == "runc":
        manager.language_pools[Language.PYTHON]._gvisor_available = False  # pylint: disable=protected-access
    yield manager
    manager.shutdown()


def _test(test_id, command, expected=None):
    if expected is None:
        return {"id": test_id, "type": "dont_fail", "name": test_id, "parameters": {"program_command": command}}
    return {"id": test_id, "type": "expect_output", "name": test_id,
            "parameters": {"program_command": command, "expected_output": expected}}


def grade(manager, tests):
    definition = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
                  "criteria": {"base": {"weight": 100, "tests": tests}}}
    pipeline = build_pipeline(definition=definition, capabilities=docker_capabilities(manager))
    files = {name: SubmissionFile(name, content) for name, content in PROGRAMS.items()}
    return pipeline.run(Submission("s", "s", "a", files, language=Language.PYTHON)).outcome


def test_default_config_assesses_every_infinite_loop_and_a_slow_correct_program(manager, runtime):
    """Four loops reach their own 30 s deadline, then a correct program uses 25 s of its own.

    The legitimate worst case (5 x 30 s) is longer than the shipped sandbox lifetime
    used to be (120 s): the reaper ended the sandbox and the grading failed with
    SANDBOX_ERROR after about 121 s instead of reporting four zeros and a 100.
    """
    tests = [_test(f"loop{index}", "python3 loop.py") for index in range(4)]
    tests.append(_test("slow", "python3 slow.py", "ok"))
    outcome = grade(manager, tests)
    assert outcome.status == "completed", outcome.error
    assert {test.id: test.score for test in outcome.tree.base.tests} == {
        "loop0": 0, "loop1": 0, "loop2": 0, "loop3": 0, "slow": 100}
    assert all("timed out" in test.report for test in outcome.tree.base.tests if test.id.startswith("loop"))
    stats = manager.get_pool_stats()["python"]
    assert stats["active"] == 0 and stats["quarantined"] == 0


def test_a_definition_beyond_the_host_maximum_is_refused_before_any_container(manager, runtime):
    """30 x 30 s needs a longer sandbox than the shipped running_timeout grants: refused, not run."""
    before = manager.client.containers.list(all=True, filters={"label": f"{LABEL_OWNER}={manager.owner.owner_id}"})
    outcome = grade(manager, [_test(f"loop{index}", "python3 loop.py") for index in range(30)])
    assert outcome.status == "failed" and outcome.score is None
    assert (outcome.error.code, outcome.error.category, outcome.error.retryable) == (
        "EXECUTION_BUDGET_EXCEEDED", "capability", False)
    after = manager.client.containers.list(all=True, filters={"label": f"{LABEL_OWNER}={manager.owner.owner_id}"})
    assert {c.id for c in after} == {c.id for c in before}
    assert manager.get_budget_stats()["held"] == 0


# ----- a sandbox ends itself: SIGKILL of its owner, nothing restarted ----------------

#: Short, so the test is quick; the production lifetime is the definition's budget.
LIFETIME = 10
#: Container creation before the grant plus Docker stopping the container afterwards.
MARGIN = 15


def _running_loop(container, deadline):
    """Block until the student program runs in ``container`` (polling Docker, bounded)."""
    while time.monotonic() < deadline:
        if container.exec_run(["pgrep", "-u", "sandbox", "python3"], user="root").exit_code == 0:
            return
    pytest.fail("the student program never started")


def _assert_stops_by_itself(container, owner, started):
    """SIGKILL the owner; the container stops within its lifetime, with nothing restarted."""
    _running_loop(container, started + 60)
    owner.kill()
    owner.wait(30)
    container.reload()
    assert container.attrs["State"]["Running"], "the owner's death must not be what stopped the sandbox"
    remaining = started + LIFETIME + MARGIN - time.monotonic()
    assert remaining > 0, "the lifetime already passed before the owner was killed; raise LIFETIME"
    try:
        status = container.wait(timeout=remaining)  # blocks on Docker; no polling sleeps
    except requests.exceptions.RequestException:
        pytest.fail(f"the sandbox outlived its lifetime of {LIFETIME}s + {MARGIN}s with its owner dead")
    assert time.monotonic() - started <= LIFETIME + MARGIN
    container.reload()
    state = container.attrs["State"]
    assert not state["Running"] and status["StatusCode"] == 137 and not state["OOMKilled"], state


def test_a_local_host_killed_mid_run_leaves_no_sandbox_beyond_its_lifetime(runtime):
    client = docker.from_env()
    started = time.monotonic()
    owner = subprocess.Popen([sys.executable, "-m", "tests.integration.lifetime_owner", "local", runtime,
                              str(LIFETIME)], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    container = None
    try:
        container = client.containers.get(owner.stdout.readline().strip())
        assert container.attrs["HostConfig"].get("Runtime") == runtime
        _assert_stops_by_itself(container, owner, started)
    finally:
        owner.kill()
        owner.wait(30)
        if container is not None:
            container.remove(force=True, v=True)
        client.close()


def test_a_sandbox_service_killed_mid_run_leaves_no_sandbox_beyond_its_lifetime(runtime):
    client = docker.from_env()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    service = subprocess.Popen([sys.executable, "-m", "tests.integration.lifetime_owner", "service", runtime,
                                str(listener.fileno())], cwd=ROOT, pass_fds=(listener.fileno(),))
    listener.close()
    container = None
    try:
        deadline = time.monotonic() + 60
        while True:
            assert service.poll() is None and time.monotonic() < deadline, "the sandbox service did not start"
            try:
                if requests.get(url + "/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
        remote = RemoteSandboxManager(url, lifetime_owner.TOKEN)
        started = time.monotonic()
        sandbox = remote.get_sandbox(Language.PYTHON, lifetime_seconds=LIFETIME)
        sandbox.prepare_workdir({"loop.py": SubmissionFile("loop.py", lifetime_owner.LOOP)})
        [container] = [item for item in client.containers.list(filters=APP_FILTER)
                       if f":{service.pid}:" in item.labels.get(LABEL_OWNER_PROCESS, "")]
        assert container.attrs["HostConfig"].get("Runtime") == runtime
        # The process request stays open until the service dies; its outcome is unknown.
        threading.Thread(target=lambda: _ignore(sandbox.run_process, ProcessRequest.command(
            "python3 loop.py", timeout=600)), daemon=True).start()
        _assert_stops_by_itself(container, service, started)
    finally:
        service.kill()
        service.wait(30)
        if container is not None:
            container.remove(force=True, v=True)
        client.close()


def _ignore(function, *args):
    try:
        function(*args)
    except Exception:  # pylint: disable=broad-exception-caught
        pass  # the service was killed under it
