"""Who ended a run: the host or the submission (COR-01), in real containers.

Every test runs under each runtime this daemon offers: gVisor (``runsc``) when
it is installed, and Docker's default runtime (``runc``), forced. A host that
stops or removes a sandbox under a correct program is an infrastructure
failure with no score. A submission that exhausts its sandbox, signals what it
can reach or deletes its entry point gets one documented assessed result, the
same under both runtimes.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument
import threading
import time

import docker
import pytest

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.language import Language
from execution_host.docker import docker_capabilities
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from tests.sandbox_profiles import TEST_IMAGES

#: Repetitions of each exhaustion program per runtime (the acceptance criterion asks for 20).
REPETITIONS = 20

PROGRAMS = {
    "correct.py": "print('ok')\n",
    # Correct, but slower than the reaper's running_timeout below.
    "slow.py": "import time\ntime.sleep(25)\nprint('ok')\n",
    # Correct, and blocks until something outside stops it.
    "wait.py": "import time\nprint('started', flush=True)\ntime.sleep(25)\nprint('ok')\n",
    "hog.py": "import time\nblocks = []\nwhile True: blocks.append(bytearray(16 * 1024 * 1024)); time.sleep(0.01)\n",
    # A process-count bomb with almost no memory: every fork that fails is retried.
    "bomb.sh": "b() { b | b & }\nb\nwhile :; do :; done\n",
    # Tries to signal the container's PID 1, then behaves correctly.
    "pid1.py": ("import os, signal\n"
                "try:\n    os.kill(1, signal.SIGKILL)\nexcept PermissionError:\n    print('ok')\n"),
    # Exits correctly, leaving a child that then keeps signalling every process it
    # can reach (the control execs included, if it could).
    "killer.py": ("import os, signal\n"
                  "parent = os.getpid()\n"
                  "if os.fork() == 0:\n"
                  "    os.setsid()\n"
                  "    while os.getppid() == parent: pass\n"
                  "    while True:\n"
                  "        try: os.kill(-1, signal.SIGKILL)\n"
                  "        except OSError: pass\n"
                  "print('ok')\n"),
    # Deletes the workspace entry point of a later criterion.
    "delete.py": "import os\nos.remove('run.sh')\nprint('ok')\n",
    "run.sh": "#!/bin/sh\necho ok\n",
}


def _daemon_runtimes():
    client = docker.from_env()
    try:
        offered = client.info().get("Runtimes", {})
    finally:
        client.close()
    return [runtime for runtime in ("runsc", "runc") if runtime == "runc" or runtime in offered]


def _pool(running_timeout):
    return SandboxPoolConfig(language=Language.PYTHON, image=TEST_IMAGES[Language.PYTHON], pool_size=0,
                             scale_limit=4, idle_timeout=300, running_timeout=running_timeout)


def _manager(runtime, running_timeout=120):
    manager = SandboxManager([_pool(running_timeout)])
    if runtime == "runc":
        # Force Docker's default runtime, as on a host without gVisor.
        manager.language_pools[Language.PYTHON]._gvisor_available = False  # pylint: disable=protected-access
    return manager


@pytest.fixture(scope="module", params=_daemon_runtimes())
def runtime(request):
    return request.param


@pytest.fixture(scope="module")
def manager(runtime):
    manager = _manager(runtime)
    yield manager
    manager.shutdown()


def _test(test_id, command, expected=None):
    if expected is None:
        return {"id": test_id, "type": "dont_fail", "name": test_id, "parameters": {"program_command": command}}
    return {"id": test_id, "type": "expect_output", "name": test_id,
            "parameters": {"program_command": command, "expected_output": expected}}


def grade(manager, tests, files=tuple(PROGRAMS)):
    definition = {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
                  "criteria": {"base": {"weight": 100, "tests": tests}}}
    pipeline = build_pipeline(definition=definition, capabilities=docker_capabilities(manager))
    submission = Submission("s", "s", "a", {name: SubmissionFile(name, PROGRAMS[name]) for name in files},
                            language=Language.PYTHON)
    return pipeline.run(submission).outcome


def scores(outcome):
    assert outcome.status == "completed", outcome.error
    return {test.id: test.score for test in outcome.tree.base.tests}


def reports(outcome):
    return {test.id: test.report for test in outcome.tree.base.tests}


def assert_runtime(manager, runtime):
    """The matrix is real: the sandbox ran on the runtime under test."""
    client = manager.client
    names = [container.attrs["HostConfig"].get("Runtime")
             for container in client.containers.list(all=True, filters={"label": f"autograder.sandbox.owner={manager.owner.owner_id}"})]
    assert not names or set(names) == {runtime}, names


# ----- the host stopped or removed the sandbox: never a score ------------------------

def _grade_while(manager, tests, interrupt):
    """Grade in a thread; once the student program is visibly running, call ``interrupt``."""
    pool = manager.language_pools[Language.PYTHON]
    result = {}
    worker = threading.Thread(target=lambda: result.setdefault("outcome", grade(manager, tests)), daemon=True)
    worker.start()
    deadline = time.monotonic() + 60
    sandbox = None
    while time.monotonic() < deadline:
        active = list(pool.active_sandboxes)
        if active:
            sandbox = active[0]
            try:
                found = sandbox.container_ref.exec_run(["pgrep", "-f", "[w]ait.py"], user="root").exit_code == 0
            except docker.errors.APIError:
                found = False  # not started yet
            if found:
                break
        time.sleep(0.05)
    else:
        pytest.fail("the student program never started")
    interrupt(manager, sandbox)
    worker.join(90)
    assert not worker.is_alive()
    return result["outcome"]


def assert_infrastructure_failure(outcome):
    assert outcome.status == "failed", outcome
    assert outcome.score is None and outcome.tree is None
    assert outcome.error.code == "SANDBOX_ERROR" and outcome.error.retryable is True


def test_external_kill_during_a_correct_program_is_an_infrastructure_failure(manager, runtime):
    outcome = _grade_while(manager, [_test("first", "python3 correct.py", "ok"), _test("waits", "python3 wait.py")],
                           lambda _, sandbox: sandbox.container_ref.kill())
    assert_infrastructure_failure(outcome)


def test_external_removal_during_a_correct_program_is_an_infrastructure_failure(manager, runtime):
    outcome = _grade_while(manager, [_test("waits", "python3 wait.py")],
                           lambda _, sandbox: sandbox.container_ref.remove(force=True, v=True))
    assert_infrastructure_failure(outcome)


def test_pool_disposal_during_a_correct_program_is_an_infrastructure_failure(manager, runtime):
    outcome = _grade_while(manager, [_test("waits", "python3 wait.py")],
                           lambda manager, sandbox: manager.dispose(sandbox))
    assert_infrastructure_failure(outcome)


def test_the_reaper_never_turns_a_correct_program_into_a_zero(runtime):
    """running_timeout passes during the second of two correct criteria."""
    manager = _manager(runtime, running_timeout=3)
    try:
        outcome = grade(manager, [_test("quick", "python3 correct.py", "ok"), _test("slow", "python3 slow.py", "ok")])
    finally:
        manager.shutdown()
    assert_infrastructure_failure(outcome)


# ----- the submission's own actions: one assessed result -----------------------------

def test_student_cannot_signal_pid_1(manager, runtime):
    outcome = grade(manager, [_test("pid1", "python3 pid1.py", "ok"), _test("after", "python3 correct.py", "ok")])
    assert scores(outcome) == {"pid1": 100, "after": 100}
    assert_runtime(manager, runtime)


def test_student_cannot_signal_the_control_processes(manager, runtime):
    outcome = grade(manager, [_test("killer", "python3 killer.py", "ok"), _test("after", "python3 correct.py", "ok")])
    assert scores(outcome) == {"killer": 100, "after": 100}


def test_a_deleted_entry_point_is_an_assessed_zero(manager, runtime):
    outcome = grade(manager, [_test("delete", "python3 delete.py", "ok"), _test("entry", "./run.sh", "ok"),
                              _test("after", "python3 correct.py", "ok")])
    assert scores(outcome) == {"delete": 100, "entry": 0, "after": 100}
    assert "./run.sh" in reports(outcome)["entry"]


def test_a_non_executable_entry_point_is_an_assessed_zero(manager, runtime):
    # Staged submission files are not executable.
    outcome = grade(manager, [_test("entry", "./run.sh", "ok")])
    assert scores(outcome) == {"entry": 0}


def test_a_missing_runtime_command_stays_a_capability_failure(manager, runtime):
    outcome = grade(manager, [_test("missing", "no-such-runtime main.py", "ok")])
    assert outcome.status == "failed" and outcome.score is None
    assert outcome.error.code == "PROCESS_START_FAILED"


EXHAUSTION = {"memory": "python3 hog.py", "processes": "sh bomb.sh"}


@pytest.mark.parametrize("repetition", range(REPETITIONS))
@pytest.mark.parametrize("kind", sorted(EXHAUSTION))
def test_exhaustion_is_one_assessed_result_and_ends_the_sandbox(manager, runtime, kind, repetition):
    outcome = grade(manager, [_test("before", "python3 correct.py", "ok"), _test("exhausts", EXHAUSTION[kind]),
                              _test("after", "python3 correct.py", "ok")])
    assert scores(outcome) == {"before": 100, "exhausts": 0, "after": 0}
    text = reports(outcome)
    assert text["exhausts"] == text["after"] and "memory or process limit" in text["exhausts"]
    stats = manager.get_pool_stats()["python"]
    assert stats["quarantined"] == 0 and stats["active"] == 0
