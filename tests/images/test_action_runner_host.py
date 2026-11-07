"""ENV-03: the packaged Action grades execution-based work on the runner's own Docker.

These tests run the Action image the way a GitHub runner runs a container
action: workspace at ``/github/workspace``, ``runs.env`` from ``action.yml``,
the runner's Docker socket mounted at ``/var/run/docker.sock`` (a hosted runner
does this for every container action). Grading happens in the image's own
process, never in-process here, and every sandbox it creates on the daemon is
observed through Docker: one sandbox of the selected language per run, removed
before the Action exits on success, on a failed grading and on ``SIGTERM``.
Without a Docker socket the Action fails with the documented error.

``make test-images`` builds the Action image and the Python runtime image first.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import yaml

from scripts.action_fixtures import PROBE
from tests.images.test_service_and_action_images import ROOT, action_environment, docker, image, run as run_in

RUNTIMES = yaml.safe_load((ROOT / "sandbox_config.yml").read_text(encoding="utf-8"))["runtimes"]
PYTHON_IO = json.loads((ROOT / "examples/definitions/python-io.json").read_text(encoding="utf-8"))
SUM = "a = int(input())\nb = int(input())\nprint(a + b)\n"
OWNER_HOST_LABEL = "autograder.sandbox.owner_host"
DOCUMENTED_ERROR = "Docker is not available to the Action"
#: Credentials a runner may hand a container action; none may reach a submission.
SENTINELS = {
    "AUTOGRADER_CLOUD_TOKEN": "ENV03-SENTINEL-CLOUD-TOKEN",
    "INPUT_AUTOGRADER-CLOUD-TOKEN": "ENV03-SENTINEL-INPUT-TOKEN",
    "GITHUB_TOKEN": "ENV03-SENTINEL-GITHUB-TOKEN",
    "ACTIONS_RUNTIME_TOKEN": "ENV03-SENTINEL-RUNTIME-TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "ENV03-SENTINEL-OIDC-TOKEN",
    "OPENAI_API_KEY": "ENV03-SENTINEL-PROVIDER-KEY",
}


@pytest.fixture(scope="module", autouse=True)
def python_runtime():
    reference = RUNTIMES["python"]
    assert docker("image", "inspect", reference, check=False).returncode == 0, (
        f"{reference} is missing: run `make test-images` (it builds the Python runtime first)")


class Run:
    """One Action container on this daemon; its sandboxes carry its unique hostname as owner."""

    def __init__(self, tmp_path: Path, definition: dict, files: dict, *, socket: bool = True, env: dict = None):
        self.tmp_path = tmp_path
        self.workspace = tmp_path / "workspace"
        (self.workspace / ".github/autograder").mkdir(parents=True)
        (self.workspace / ".github/autograder/definition.json").write_text(json.dumps(definition), encoding="utf-8")
        for filename, content in files.items():
            (self.workspace / filename).write_text(content, encoding="utf-8")
        self.commands = tmp_path / "file_commands"
        self.commands.mkdir()
        self.name = f"env03-action-{uuid.uuid4().hex[:12]}"
        self.started = str(int(time.time()) - 1)
        environment = {**action_environment(), "GITHUB_WORKSPACE": "/github/workspace", "GITHUB_ACTIONS": "true",
                       "GITHUB_OUTPUT": "/github/file_commands/output",
                       "GITHUB_STEP_SUMMARY": "/github/file_commands/summary", **(env or {})}
        self.arguments = ["run", "--name", self.name, "--hostname", self.name, "--workdir", "/github/workspace",
                          "--security-opt", "label=disable",
                          "--volume", f"{self.workspace}:/github/workspace",
                          "--volume", f"{self.commands}:/github/file_commands"]
        if socket:
            self.arguments += ["--volume", "/var/run/docker.sock:/var/run/docker.sock"]
        for variable, value in environment.items():
            self.arguments += ["--env", f"{variable}={value}"]
        self.arguments.append(image("action"))

    def run(self) -> subprocess.CompletedProcess:
        return docker(*self.arguments, check=False, timeout=300)

    def start(self) -> None:
        docker(*self.arguments[:1], "--detach", *self.arguments[1:])

    def sandboxes(self) -> list:
        """Sandbox containers of this run that still exist."""
        return docker("ps", "--all", "--quiet", "--filter", f"label={OWNER_HOST_LABEL}={self.name}").stdout.split()

    def created(self) -> list:
        """The image of every sandbox this run created, from the daemon's event log."""
        events = docker("events", "--since", self.started, "--until", str(int(time.time()) + 1),
                        "--filter", "type=container", "--filter", "event=create",
                        "--filter", f"label={OWNER_HOST_LABEL}={self.name}",
                        "--format", "{{.Actor.Attributes.image}}")
        return events.stdout.split()

    def outcome(self) -> dict:
        return json.loads((self.workspace / ".autograder/outcome.json").read_text(encoding="utf-8"))

    def close(self) -> None:
        docker("rm", "--force", self.name, check=False)
        for container in self.sandboxes():
            docker("rm", "--force", container, check=False)
        # The action runs as root, as on a hosted runner: hand the files back to this user.
        docker("run", "--rm", "--network", "none", "--entrypoint", "chown", "--volume", f"{self.tmp_path}:/work",
               image("action"), "-R", f"{os.getuid()}:{os.getgid()}", "/work", check=False)


@pytest.fixture
def action_run(tmp_path):
    runs = []

    def make(definition, files, **options):
        runs.append(Run(tmp_path / f"run{len(runs)}", definition, files, **options))
        return runs[-1]

    yield make
    for run in runs:
        run.close()


def test_action_image_pins_the_runtime_images_of_its_release():
    shipped = yaml.safe_load(run_in(image("action"), "cat", "/app/sandbox_config.yml"))["runtimes"]
    assert shipped == RUNTIMES
    for reference in shipped.values():
        assert re.fullmatch(r"ghcr\.io/webtech-network/autograder-sandbox-[a-z]+:[0-9a-f]{12}", reference), reference


def test_action_grades_execution_in_one_sandbox_of_the_selected_language(action_run):
    run = action_run(PYTHON_IO, {"main.py": SUM})
    result = run.run()
    assert result.returncode == 0, result.stdout + result.stderr
    outcome = run.outcome()
    assert (outcome["status"], outcome["score"]) == ("completed", 100)
    assert "status=completed" in (run.commands / "output").read_text(encoding="utf-8")
    # Only the selected language's runtime, once, on demand: no pool, no warm-up of other runtimes.
    assert run.created() == [RUNTIMES["python"]]
    assert run.sandboxes() == []


def test_failed_grading_still_removes_its_sandbox(action_run):
    definition = json.loads(json.dumps(PYTHON_IO))
    definition["preparation"]["languages"]["python"]["setup_commands"] = [
        {"name": "Refuse", "command": "python3 -c 'raise SystemExit(3)'"}]
    run = action_run(definition, {"main.py": SUM})
    result = run.run()
    assert result.returncode == 1, result.stdout + result.stderr
    outcome = run.outcome()
    assert outcome["status"] == "failed" and outcome["error"]["code"] == "PREPARATION_FAILED", outcome["error"]
    assert run.created() == [RUNTIMES["python"]]
    assert run.sandboxes() == []


def test_sigterm_during_grading_removes_the_sandbox_before_the_action_exits(action_run):
    run = action_run(PYTHON_IO, {"main.py": "import time\ntime.sleep(600)\n"})
    run.start()
    deadline = time.monotonic() + 120
    while not run.sandboxes():  # waits for a condition (the sandbox exists), not for time
        state = docker("inspect", "--format", "{{.State.Running}}", run.name).stdout.strip()
        assert state == "true", docker("logs", run.name).stderr
        assert time.monotonic() < deadline, "the Action never acquired a sandbox"
        time.sleep(0.2)
    docker("kill", "--signal", "TERM", run.name)
    status = docker("wait", run.name, timeout=120).stdout.strip()
    assert status == "143", docker("logs", run.name).stderr  # 128 + SIGTERM, after the finally blocks ran
    assert run.sandboxes() == []
    assert run.created() == [RUNTIMES["python"]]


def test_without_docker_execution_fails_with_the_documented_error(action_run):
    run = action_run(PYTHON_IO, {"main.py": SUM}, socket=False)
    result = run.run()
    assert result.returncode == 1
    assert DOCUMENTED_ERROR in result.stderr, result.stderr
    assert "CAPABILITY_UNAVAILABLE" not in result.stdout + result.stderr
    assert not (run.workspace / ".autograder/outcome.json").exists()  # nothing was graded


def test_submission_cannot_see_credentials_runner_environment_socket_or_network(action_run):
    definition = json.loads((ROOT / "examples/contracts/input_output.json").read_text(encoding="utf-8"))
    run = action_run(definition, {"main.py": PROBE}, env=SENTINELS)
    result = run.run()
    assert result.returncode == 0, result.stdout + result.stderr
    outcome = run.outcome()
    assert (outcome["status"], outcome["score"]) == ("completed", 0)  # the probe's output is not the echo
    report = outcome["tree"]["base"]["tests"][0]["report"]
    seen = json.loads(report.split("Actual: '", 1)[1].rsplit("'", 1)[0])
    assert seen["cwd"] == "/app" and seen["files"] == ["main.py"]
    assert not [name for name in seen["variables"] if name.startswith(("GITHUB_", "RUNNER_", "ACTIONS_", "INPUT_"))]
    for name, value in SENTINELS.items():
        assert name not in seen["variables"]
        assert value not in seen["environment"] and value not in seen["pid1_environ"]
        assert value not in json.dumps(outcome)
    assert seen["docker_socket"] is False
    assert seen["network"] != "connected"
    assert run.sandboxes() == []


def test_action_pulls_a_runtime_image_the_runner_does_not_have(action_run, tmp_path):
    """Zero setup: the pinned runtime reference is pulled by the Action itself (here from a local registry)."""
    registry = f"env03-registry-{uuid.uuid4().hex[:8]}"
    docker("run", "--detach", "--name", registry, "--publish", "127.0.0.1::5000", "registry:2.8.3")
    reference = None
    try:
        port = docker("port", registry, "5000/tcp").stdout.split(":")[-1].strip()
        reference = f"127.0.0.1:{port}/env03/autograder-sandbox-python:{uuid.uuid4().hex[:12]}"
        docker("tag", RUNTIMES["python"], reference)
        deadline = time.monotonic() + 60
        while docker("push", reference, check=False).returncode != 0:  # until the registry accepts pushes
            assert time.monotonic() < deadline, "the local registry never accepted the push"
            time.sleep(0.5)
        docker("image", "rm", reference)
        config = tmp_path / "sandbox_config.yml"
        config.write_text((ROOT / "sandbox_config.yml").read_text(encoding="utf-8").replace(
            RUNTIMES["python"], reference), encoding="utf-8")
        run = action_run(PYTHON_IO, {"main.py": SUM})
        run.arguments[-1:-1] = ["--volume", f"{config}:/app/sandbox_config.yml:ro"]
        result = run.run()
        assert result.returncode == 0, result.stdout + result.stderr
        assert (run.outcome()["status"], run.outcome()["score"]) == ("completed", 100)
        assert run.created() == [reference]
        assert docker("image", "inspect", reference, check=False).returncode == 0  # pulled by the Action
    finally:
        docker("rm", "--force", "--volumes", registry, check=False)
        if reference:
            docker("image", "rm", "--force", reference, check=False)


def test_the_documented_definition_check_runs_from_the_action_image(tmp_path):
    """ONB-06: the optional CI step of the Action quick start, as a course repository runs it:
    the Action image's own Python checks the definition and grades the reference solution in a
    sandbox on the runner's Docker; a broken definition fails the step with the error's path."""
    workspace = tmp_path / "course"
    (workspace / ".github/autograder").mkdir(parents=True)
    (workspace / ".github/autograder/definition.json").write_text(json.dumps(PYTHON_IO), encoding="utf-8")
    (workspace / "solution").mkdir()
    (workspace / "solution/main.py").write_text(SUM, encoding="utf-8")
    broken = json.loads(json.dumps(PYTHON_IO))
    broken["templates"] = ["input_outptu"]
    (workspace / "broken.json").write_text(json.dumps(broken), encoding="utf-8")
    name = f"onb06-check-{uuid.uuid4().hex[:12]}"

    def step(*arguments):
        return docker("run", "--rm", "--name", name, "--hostname", name, "--security-opt", "label=disable",
                      "--volume", f"{workspace}:/work", "--workdir", "/work",
                      "--volume", "/var/run/docker.sock:/var/run/docker.sock",
                      "--entrypoint", "python", image("action"), "-m", "execution_host.check", *arguments,
                      check=False, timeout=300)

    try:
        result = step(".github/autograder/definition.json", "--submission", "solution", "--min-score", "100")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "python: 1 process, sandbox lifetime up to 92 s; this host grants 900 s" in result.stdout
        assert "Reference solution (python): completed, score 100.00/100" in result.stdout
        result = step("broken.json")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "templates[0]: Unknown template `input_outptu`; did you mean `input_output`?" in result.stdout
    finally:
        docker("rm", "--force", name, check=False)
        sandboxes = docker("ps", "--all", "--quiet", "--filter", f"label={OWNER_HOST_LABEL}={name}").stdout.split()
        for container in sandboxes:
            docker("rm", "--force", container, check=False)
    assert sandboxes == []  # the sandbox was removed before the check exited
