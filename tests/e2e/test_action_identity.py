"""INT-02 end to end: the real Action grades in Docker and publishes with a restricted
producer token to a real API process. A rerun by someone else preserves ownership."""
import json
from pathlib import Path
import subprocess

import pytest
import requests

from github_action import main as action_main
from github_action.identity import TrustError
from tests.e2e.contracts import create_config
from tests.sandbox_profiles import sandbox_config

DEFINITION = json.loads((Path(__file__).resolve().parents[2] / "examples/contracts/input_output.json").read_text())


@pytest.fixture
def checkout(tmp_path, monkeypatch, isolated_api):
    docker = pytest.importorskip("docker")
    try:
        docker.from_env().images.get("sandbox-py")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"sandbox-py image required: {exc}")
    workspace = tmp_path / "checkout"
    (workspace / ".github/autograder").mkdir(parents=True)
    (workspace / ".github/autograder/definition.json").write_text(json.dumps(DEFINITION))
    (workspace / "main.py").write_text("print(input())\n")
    environment = {"GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@x", "GIT_COMMITTER_NAME": "a",
                   "GIT_COMMITTER_EMAIL": "a@x", "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    for command in (["init", "-q"], ["add", "."], ["commit", "-qm", "solution"]):
        subprocess.run(["git", "-C", str(workspace), *command], check=True, env=environment)
    head = subprocess.run(["git", "-C", str(workspace), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    sandbox = tmp_path / "sandbox.yml"
    sandbox.write_text(sandbox_config())
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("SANDBOX_MODE", "local")
    monkeypatch.setenv("SANDBOX_CONFIG_FILE", str(sandbox))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    # A hosted push run in a student's repository.
    for name, value in {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                        "GITHUB_EVENT_NAME": "push", "GITHUB_REPOSITORY": "classroom/hello-alice",
                        "GITHUB_REPOSITORY_ID": "424242", "GITHUB_SHA": head, "GITHUB_REF": "refs/heads/main",
                        "GITHUB_RUN_ID": "9001", "GITHUB_WORKFLOW_REF": "classroom/hello-alice/.github/workflows/grade.yml@refs/heads/main"}.items():
        monkeypatch.setenv(name, value)
    return workspace, head


def run_attempt(monkeypatch, workspace, url, token, config, *, attempt, actor, extra=()):
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(attempt))
    monkeypatch.setenv("GITHUB_ACTOR", "alice")
    monkeypatch.setenv("GITHUB_TRIGGERING_ACTOR", actor)
    outputs = workspace.parent / f"outputs-{attempt}"
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    args = ["--upload-to-cloud", "true", "--grading-config-id", str(config["id"]),
            "--grading-config-revision", str(config["version"]), "--autograder-cloud-url", url,
            "--autograder-cloud-token", token, *extra]
    assert action_main.run(action_main.parser.parse_args(args)) is True
    lines = outputs.read_text().splitlines()
    return int(next(line for line in lines if line.startswith("submission-id=")).split("=", 1)[1])


def details(api_base_url, auth_headers, submission_id):
    response = requests.get(f"{api_base_url}/submissions/{submission_id}/details", headers=auth_headers, timeout=5)
    assert response.status_code == 200
    return response.json()


def test_prisma_identity_survives_instructor_rerun(checkout, monkeypatch, api_base_url, auth_headers, isolated_api):
    workspace, head = checkout
    url, token = api_base_url.removesuffix("/api/v1"), isolated_api["producer_token"]
    config = create_config(api_base_url, auth_headers, DEFINITION)
    identity = ["--submitter-id", "prisma:student:alice-01", "--submitter-name", "Alice"]
    first = run_attempt(monkeypatch, workspace, url, token, config, attempt=1, actor="alice", extra=identity)
    # Retrying delivery of attempt 1 reuses its identity and receipt.
    saved = workspace / ".autograder/delivery.json"
    retry = action_main.parser.parse_args(["--retry-delivery-path", str(saved), "--autograder-cloud-url", url,
                                           "--autograder-cloud-token", token])
    assert action_main.run(retry) is True
    assert f"submission-id={first}" in (workspace.parent / "outputs-1").read_text().splitlines()[-1]
    # Instructor Bob re-runs the workflow: attempt 2 is a new execution of Alice's work.
    second = run_attempt(monkeypatch, workspace, url, token, config, attempt=2, actor="instructor-bob", extra=identity)
    assert second != first
    for submission_id, attempt, actor in ((first, "1", "alice"), (second, "2", "instructor-bob")):
        stored = details(api_base_url, auth_headers, submission_id)
        assert stored["external_user_id"] == "prisma:student:alice-01" and stored["username"] == "Alice"
        assert stored["status"] == "completed" and stored["final_score"] == 100
        github = stored["submission_metadata"]["github"]
        assert github["run_id"] == "9001" and github["run_attempt"] == attempt
        assert github["triggering_actor"] == actor and github["actor"] == "alice"
        assert github["evaluated_commit"] == head == github["event_sha"]
        assert github["evaluated_tree_matches_commit"] is True
        assert stored["submission_metadata"]["submitter_source"] == "input"
        assert token not in json.dumps(stored) and isolated_api["token"] not in json.dumps(stored)
        # An attestation is a producer claim: it carries no files and is not a server execution.
        assert stored["submission_files"] == {}
    history = requests.get(api_base_url + "/submissions/user/prisma:student:alice-01", headers=auth_headers,
                           timeout=5).json()
    assert sorted(item["id"] for item in history) == sorted([first, second])
    assert not requests.get(api_base_url + "/submissions/user/instructor-bob", headers=auth_headers, timeout=5).json()


def test_repository_owns_work_without_explicit_submitter(checkout, monkeypatch, api_base_url, auth_headers,
                                                         isolated_api):
    workspace, _ = checkout
    config = create_config(api_base_url, auth_headers, DEFINITION)
    submission_id = run_attempt(monkeypatch, workspace, api_base_url.removesuffix("/api/v1"),
                                isolated_api["producer_token"], config, attempt=1, actor="instructor-bob")
    stored = details(api_base_url, auth_headers, submission_id)
    assert stored["external_user_id"] == "github-repository:424242"
    assert stored["username"] == "classroom/hello-alice"
    assert stored["submission_metadata"]["submitter_source"] == "repository"


def test_uncommitted_changes_are_recorded(checkout, monkeypatch, api_base_url, auth_headers, isolated_api):
    workspace, head = checkout
    (workspace / "main.py").write_text("print(input())  # edited after checkout\n")
    config = create_config(api_base_url, auth_headers, DEFINITION)
    submission_id = run_attempt(monkeypatch, workspace, api_base_url.removesuffix("/api/v1"),
                                isolated_api["producer_token"], config, attempt=1, actor="alice")
    github = details(api_base_url, auth_headers, submission_id)["submission_metadata"]["github"]
    assert github["evaluated_commit"] == head and github["evaluated_tree_matches_commit"] is False


def test_untrusted_event_cannot_publish(checkout, monkeypatch, api_base_url, auth_headers, isolated_api):
    workspace, _ = checkout
    config = create_config(api_base_url, auth_headers, DEFINITION)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    with pytest.raises(TrustError):
        run_attempt(monkeypatch, workspace, api_base_url.removesuffix("/api/v1"), isolated_api["producer_token"],
                    config, attempt=1, actor="fork-author")
    assert not (workspace / ".autograder/outcome.json").exists()  # refused before grading


def test_restricted_token_cannot_use_external_mode(checkout, monkeypatch, api_base_url, auth_headers, isolated_api):
    workspace, _ = checkout
    config = create_config(api_base_url, auth_headers, DEFINITION)
    args = action_main.parser.parse_args(["--execution-mode", "external", "--grading-config-id", str(config["id"]),
                                          "--autograder-cloud-url", api_base_url.removesuffix("/api/v1"),
                                          "--autograder-cloud-token", isolated_api["producer_token"]])
    from github_action.cloud_client import CloudClientError
    with pytest.raises(CloudClientError) as error:
        action_main.run(args)
    assert error.value.status_code == 403
