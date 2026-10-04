"""Actions contract regressions exercise retained artifacts before publication."""
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml

from github_action import main


def completed():
    return {"schema_version": "1.0", "status": "completed", "score": 100.0,
            "execution_id": "action-test", "language": "node",
            "provenance": {"definition_hash": "a" * 64},
            "started_at": "2026-10-04T10:00:00Z", "finished_at": "2026-10-04T10:00:01Z",
            "duration_ms": 1000, "tree": {"score": 100, "base": {"name": "base", "weight": 100,
                "score": 100, "tests": [{"id": "entry", "evaluator": "check_project_structure",
                    "name": "HTML entry", "weight": 100, "score": 100}]}},
            "feedback": {"status": "completed", "content": "Feedback"}}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<header>ok</header>")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    return tmp_path


def test_delivery_failure_retains_grade_and_never_uploads_failure(workspace):
    service = MagicMock()
    service.run_autograder.return_value.model_dump.return_value = completed()
    service.delivery_payload.return_value = {"outcome": completed()}
    service.publish.side_effect = RuntimeError("network unavailable")
    args = main.parser.parse_args(["--execution-mode", "external", "--grading-config-id", "7",
                                  "--autograder-cloud-url", "https://cloud.invalid",
                                  "--autograder-cloud-token", "secret", "--upload-to-cloud", "true"])
    with patch.object(main, "GithubActionService", return_value=service):
        with pytest.raises(RuntimeError, match="delivery failed"):
            main.run(args)
    assert json.loads((workspace / ".autograder/outcome.json").read_text())["score"] == 100
    assert (workspace / ".autograder/delivery.json").is_file()
    assert (workspace / ".autograder/feedback.md").read_text() == "Feedback"
    assert "status=completed" in (workspace / "outputs").read_text()
    assert "score=100.0" in (workspace / "outputs").read_text()
    service.run_autograder.assert_called_once()
    service.publish.assert_called_once()
    service.submit_failure_to_cloud.assert_not_called()


def test_retry_publishes_saved_attestation_without_evaluation(workspace):
    payload = {"outcome": completed(), "grading_config_id": 7}
    (workspace / "saved.json").write_text(json.dumps(payload))
    args = main.parser.parse_args(["--retry-delivery-path", "saved.json", "--autograder-cloud-url",
                                  "https://cloud.invalid", "--autograder-cloud-token", "secret"])
    with patch.object(main, "GithubActionService") as service, patch.object(main, "CloudClient") as client:
        client.return_value.submit_external_result.return_value = {"submission_id": 23}
        assert main.run(args)
    service.assert_not_called()
    client.return_value.submit_external_result.assert_called_once_with(payload)
    assert "submission-id=23" in (workspace / "outputs").read_text()


def test_failed_grading_has_null_score_and_retained_artifact(workspace):
    service = MagicMock()
    failed = completed()
    failed.update(status="failed", score=None, tree=None, feedback={"status": "disabled"},
                  error={"code": "SANDBOX_UNAVAILABLE", "message": "Sandbox unavailable.",
                         "category": "capability", "retryable": True, "correlation_id": "action-test"})
    service.run_autograder.return_value.model_dump.return_value = failed
    service.delivery_payload.return_value = None
    with patch.object(main, "GithubActionService", return_value=service):
        assert not main.run(main.parser.parse_args([]))
    assert "status=failed" in (workspace / "outputs").read_text()
    assert "score=" not in (workspace / "outputs").read_text()
    assert (workspace / ".autograder/outcome.json").is_file()


def test_collection_ordinary_checkout_skips_action_artifacts_and_metadata(workspace):
    for folder in [".git", ".github", ".autograder"]:
        (workspace / folder).mkdir()
        (workspace / folder / "secret.txt").write_text("do not grade")
    assert list(main.collect_files(workspace)) == ["index.html"]


def test_invalid_root_and_non_text_file_fail_clearly(workspace):
    with pytest.raises(ValueError, match="existing readable directory"):
        main.collect_files(workspace / "missing")
    (workspace / "binary").write_bytes(b"\xff")
    with pytest.raises(ValueError, match="readable UTF-8 text: binary"):
        main.collect_files(workspace)


def test_metadata_inputs_are_forwarded_by_real_shell(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    metadata = yaml.safe_load((repo / "action.yml").read_text())
    capture = tmp_path / "captured.json"
    fake = tmp_path / "python"
    fake.write_text("#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ['CAPTURE'], 'w').write(json.dumps(sys.argv[1:]))\n")
    fake.chmod(0o755)
    values = {"execution-mode": "external", "definition-path": "config with spaces.json",
              "submission-root": "source with spaces", "grading-config-id": "7",
              "autograder-cloud-url": "https://cloud.invalid", "autograder-cloud-token": "secret",
              "upload-to-cloud": "true", "retry-delivery-path": "saved.json",
              "submission-language": "python", "locale": "pt-br"}
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ["PATH"], CAPTURE=str(capture), GITHUB_ACTOR="alice")
    for variable, expression in metadata["runs"]["env"].items():
        name = expression.removeprefix("${{ inputs.").removesuffix(" }}")
        assert name in metadata["inputs"]
        env[variable] = values[name]
    subprocess.run(["bash", str(repo / "github_action/entrypoint.sh")], env=env, check=True)
    argv = json.loads(capture.read_text())
    assert argv[:2] == ["-m", "github_action.main"]
    parsed = vars(main.parser.parse_args(argv[2:]))
    for name, value in values.items():
        assert str(parsed[name.replace("-", "_")]) == value
    assert parsed["student_name"] == "alice"


def test_real_shell_grades_ordinary_checkout_and_retains_canonical_outcome(workspace):
    import sys
    from autograder.models.contracts.outcome import validate_outcome
    from tests.unit.github_action.test_github_action_service import definition
    repo = Path(__file__).resolve().parents[3]
    path = workspace / ".github/autograder/definition.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(definition()))
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
               GITHUB_ACTOR="alice", LOCALE="pt-br", EXECUTION_MODE="repo",
               DEFINITION_PATH=".github/autograder/definition.json", SUBMISSION_ROOT=".",
               UPLOAD_TO_CLOUD="false")
    # Output/summary fixtures belong outside the submission under assessment.
    env["GITHUB_OUTPUT"] = str(workspace.parent / "real-output")
    env["GITHUB_STEP_SUMMARY"] = str(workspace.parent / "real-summary")
    result = subprocess.run(["bash", str(repo / "github_action/entrypoint.sh")], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    outcome = validate_outcome(json.loads((workspace / ".autograder/outcome.json").read_text()))
    assert outcome.status == "completed"
    assert outcome.score == 100
    assert outcome.language == "node"
    assert outcome.provenance.definition_hash
    assert "result-path=.autograder/outcome.json" in Path(env["GITHUB_OUTPUT"]).read_text()


@pytest.mark.parametrize("delivery_fails", [False, True])
def test_external_metadata_shell_cli_real_wire_outcome(workspace, delivery_fails):
    """Start from action metadata and run the real CLI against a local cloud seam."""
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from autograder.models.contracts.definition import compile_definition
    from autograder.models.contracts.outcome import validate_outcome
    from tests.unit.github_action.test_github_action_service import definition
    from web.schemas.submission import ExternalResultCreate
    repo = Path(__file__).resolve().parents[3]
    metadata = yaml.safe_load((repo / "action.yml").read_text())
    value = definition()
    value["feedback"] = {"enabled": True}
    compiled = compile_definition(value)
    config = {"id": 7, "version": 3, "definition": compiled.definition.model_dump(mode="json"),
              "definition_hash": compiled.definition_hash}
    requests_seen, uploaded, errors = [], [], []

    class Cloud(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            requests_seen.append(("GET", self.path))
            if self.path != "/api/v1/configs/id/7" or self.headers.get("Authorization") != "Bearer cloud-secret":
                errors.append("Wrong configuration request/authentication")
                self.respond(400, {})
                return
            self.respond(200, config)

        def do_POST(self):
            requests_seen.append(("POST", self.path))
            try:
                assert self.path == "/api/v1/submissions/external-results"
                assert self.headers.get("Authorization") == "Bearer cloud-secret"
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                ExternalResultCreate.model_validate(payload)
                saved = json.loads((workspace / ".autograder/outcome.json").read_text())
                assert payload["outcome"] == saved  # artifact precedes network delivery
                assert json.loads((workspace / ".autograder/delivery.json").read_text()) == payload
                assert payload["definition_snapshot"] == config["definition"]
                assert payload["outcome"]["provenance"] == {
                    "schema_version": "1.0", "definition_hash": compiled.definition_hash,
                    "reference": "7", "revision": 3}
                assert payload["external_user_id"] == "alice"
                assert payload["language"] == "node"
                assert "Relatório de Avaliação" in payload["outcome"]["feedback"]["content"]
                uploaded.append(payload)
            except Exception as exc:
                errors.append(str(exc))
                self.respond(400, {})
                return
            self.respond(503 if delivery_fails else 200, {} if delivery_fails else {"submission_id": 42})

        def log_message(self, *args):
            pass

    source = workspace / "source"
    source.mkdir()
    (source / "index.html").write_text("<header>ok</header>")
    with ThreadingHTTPServer(("127.0.0.1", 0), Cloud) as cloud:
        thread = threading.Thread(target=cloud.serve_forever, daemon=True)
        thread.start()
        values = {name: item.get("default", "") for name, item in metadata["inputs"].items()}
        values.update({"execution-mode": "external", "submission-root": "source", "grading-config-id": "7",
            "autograder-cloud-url": f"http://127.0.0.1:{cloud.server_address[1]}",
            "autograder-cloud-token": "cloud-secret", "upload-to-cloud": "true",
            "submission-language": "node", "locale": "pt-br"})
        env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"], GITHUB_ACTOR="alice")
        for variable, expression in metadata["runs"]["env"].items():
            name = expression.removeprefix("${{ inputs.").removesuffix(" }}")
            env[variable] = values[name]
        result = subprocess.run(["bash", str(repo / "github_action/entrypoint.sh")], env=env,
                                capture_output=True, text=True, timeout=30)
        cloud.shutdown()
        thread.join(timeout=5)
    assert not errors, errors
    assert result.returncode == (1 if delivery_fails else 0), result.stderr
    assert requests_seen == [("GET", "/api/v1/configs/id/7"), ("POST", "/api/v1/submissions/external-results")]
    assert len(uploaded) == 1
    assert validate_outcome(uploaded[0]["outcome"]).score == 100
    outputs = (workspace / "outputs").read_text()
    assert "status=completed" in outputs and "score=100.0" in outputs
    assert ("submission-id=42" in outputs) is not delivery_fails
    if delivery_fails:
        assert "Result delivery failed" in result.stderr
