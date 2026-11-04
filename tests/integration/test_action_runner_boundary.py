"""INT-02 with real Docker: the Action's runner capability keeps credentials out of
reach of the untrusted submission it grades, without the web host's pool lifecycle."""
import json
from pathlib import Path

import pytest

from github_action import main

PROBE = r'''
import json, os, socket
try:
    socket.create_connection(("1.1.1.1", 443), timeout=2)
    network = "reachable"
except OSError:
    network = "blocked"
seen = {
    "environment": dict(os.environ),
    "docker_socket": os.path.exists("/var/run/docker.sock"),
    "network": network,
    "workspace_files": sorted(os.listdir(".")),
}
print(json.dumps(seen, sort_keys=True))
'''

SENTINELS = {
    "AUTOGRADER_CLOUD_TOKEN": "SENTINEL-CLOUD-TOKEN-7f3a",
    "INPUT_AUTOGRADER-CLOUD-TOKEN": "SENTINEL-INPUT-TOKEN-7f3a",
    "OPENAI_API_KEY": "SENTINEL-PROVIDER-KEY-7f3a",
    "GITHUB_TOKEN": "SENTINEL-GITHUB-TOKEN-7f3a",
    "ACTIONS_RUNTIME_TOKEN": "SENTINEL-RUNTIME-TOKEN-7f3a",
}


@pytest.fixture
def action_workspace(tmp_path, monkeypatch):
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.images.get("sandbox-py")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Docker with the sandbox-py image is required: {exc}")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text(PROBE)
    definition = json.loads((Path(__file__).resolve().parents[2] / "examples/contracts/input_output.json").read_text())
    path = workspace / ".github/autograder/definition.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(definition))
    config = tmp_path / "sandbox.yml"
    config.write_text("general:\n  pool_size: 0\n  scale_limit: 2\n  idle_timeout: 300\n  running_timeout: 60\n")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("SANDBOX_MODE", "local")
    monkeypatch.setenv("SANDBOX_CONFIG_FILE", str(config))
    for name, value in SENTINELS.items():
        monkeypatch.setenv(name, value)
    return workspace


def test_submission_code_cannot_observe_runner_credentials(action_workspace):
    # The probe fails the echo criterion; the assessed report shows its stdout.
    assert main.run(main.parser.parse_args(["--submitter-id", "alice"])) is True
    outcome = json.loads((action_workspace / ".autograder/outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["score"] == 0
    report = outcome["tree"]["base"]["tests"][0]["report"]
    observed = json.loads(report.split("Actual: '", 1)[1].rsplit("'", 1)[0])
    assert observed["environment"]["PWD"] == "/app"  # the probe really ran in the sandbox
    for name, value in SENTINELS.items():
        assert name not in observed["environment"]
        assert value not in json.dumps(outcome)
    assert observed["docker_socket"] is False
    assert observed["network"] == "blocked"
    # Only submission files are staged; Action metadata and the definition are not.
    assert observed["workspace_files"] == ["main.py"]


def test_action_capability_owns_and_releases_its_sandboxes(action_workspace, monkeypatch):
    import docker
    from execution_host.docker import DockerHost

    created = []
    original = DockerHost.acquire

    def acquire(self, language):
        session = original(self, language)
        created.append(session.sandbox.container_ref.id)
        return session

    monkeypatch.setattr(DockerHost, "acquire", acquire)
    main.run(main.parser.parse_args([]))
    assert created
    client = docker.from_env()
    for container_id in created:
        # The Action host disposes every sandbox it created before returning.
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(container_id)
