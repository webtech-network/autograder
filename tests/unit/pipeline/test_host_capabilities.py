"""Selected work, explicit providers, and transfer of session ownership."""
from unittest.mock import Mock

import pytest

from autograder import build_pipeline
from autograder.models.capabilities import HostCapabilities
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import CommandResponse, Language, ResponseCategory


def definition(*, preparation=None, templates=None, evaluator="check_project_structure", parameters=None):
    return {"schema_version": "1.0", "templates": templates or ["webdev"],
            "languages": ["python", "java"],
            "criteria": {"base": {"weight": 100, "tests": [{"id": "structure", "name": "Structure",
                "type": evaluator, "parameters": parameters or {"expected_structure": "main.py"}}]}},
            "preparation": preparation or {}}


def submission(language=Language.PYTHON, files=None):
    return Submission("student", 1, 1, files if files is not None else {
        "main.py": SubmissionFile("main.py", "print('ok')")}, language=language)


def session():
    result = Mock()
    result.run_command.return_value = CommandResponse("ok", "", 0, 0)
    return result


def test_static_selected_with_unused_execution_template_needs_no_services():
    outcome = build_pipeline(definition=definition(templates=["webdev", "input_output"])).run(submission()).outcome
    assert outcome.status == "completed" and outcome.score == 100


def test_unselected_language_setup_does_not_acquire_or_run():
    acquire = Mock(side_effect=AssertionError("must not acquire"))
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"java": {
        "required_files": ["Main.java"], "setup_commands": [{"name": "compile", "command": "javac Main.java"}]}}}),
        capabilities=HostCapabilities(execution=acquire))
    assert pipeline.run(submission()).outcome.status == "completed"
    acquire.assert_not_called()


def test_required_files_fail_before_any_provider_or_provisioning():
    acquire = Mock(side_effect=AssertionError("must not acquire"))
    fixtures = Mock(side_effect=AssertionError("must not fetch"))
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "required_files": ["missing.py"], "setup_commands": [{"name": "run", "command": "true"}]}},
        "fixtures": [{"reference": "fixture", "path": "data.bin"}]}),
        capabilities=HostCapabilities(execution=acquire, fixtures=fixtures))
    outcome = pipeline.run(submission()).outcome
    assert outcome.status == "failed" and outcome.error.code == "REQUIRED_FILE_MISSING"
    acquire.assert_not_called()
    fixtures.assert_not_called()


def test_setup_and_empty_fixture_use_selected_session_then_close_before_outcome():
    owned = session()
    events = []
    owned.close.side_effect = lambda: events.append("closed")
    acquire = Mock(return_value=owned)
    fixtures = Mock(return_value=b"")
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "setup", "command": "prepare"}]}},
        "fixtures": [{"reference": "datasets/empty", "path": "data.bin"}]}),
        capabilities=HostCapabilities(execution=acquire, fixtures=fixtures))
    execution = pipeline.run(submission())
    assert execution.outcome.status == "completed" and events == ["closed"]
    acquire.assert_called_once_with(Language.PYTHON)
    owned.stage_fixture.assert_called_once_with("data.bin", b"", True)
    owned.run_command.assert_called_once_with("prepare")
    owned.close.assert_called_once()
    assert execution.sandbox is None


@pytest.mark.parametrize("operation", ["prepare_workdir", "stage_fixture", "run_command"])
def test_failure_after_ownership_transfer_closes_once(operation):
    owned = session()
    getattr(owned, operation).side_effect = RuntimeError("private details")
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "setup", "command": "prepare"}]}},
        "fixtures": [{"reference": "fixture", "path": "file"}]}),
        capabilities=HostCapabilities(execution=lambda language: owned, fixtures=lambda reference: b"data"))
    outcome = pipeline.run(submission()).outcome
    assert outcome.status == "failed" and outcome.score is None
    assert "private" not in outcome.error.message
    owned.close.assert_called_once()


def test_acquisition_failure_transfers_no_session():
    acquire = Mock(side_effect=RuntimeError("private pool error"))
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "setup", "command": "prepare"}]}}}),
        capabilities=HostCapabilities(execution=acquire))
    result = pipeline.run(submission())
    assert result.sandbox is None and result.outcome.error.code == "CAPABILITY_UNAVAILABLE"


def test_setup_student_failure_stops_before_assessment():
    owned = session()
    owned.run_command.return_value = CommandResponse("", "compile error", 1, 0, ResponseCategory.COMPILATION_ERROR)
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "setup", "command": "prepare"}]}}}),
        capabilities=HostCapabilities(execution=lambda language: owned))
    outcome = pipeline.run(submission()).outcome
    assert outcome.status == "failed" and outcome.score is None
    assert outcome.error.code == "PREPARATION_FAILED"
    owned.close.assert_called_once()


def test_api_missing_server_capability_fails_before_acquiring_or_scoring():
    acquire = Mock()
    value = definition(templates=["api"], evaluator="health_check",
                       parameters={"endpoint": "/"})
    pipeline = build_pipeline(definition=value, capabilities=HostCapabilities(execution=acquire))
    outcome = pipeline.run(submission()).outcome
    assert outcome.error.code == "SERVER_CAPABILITY_UNAVAILABLE" and outcome.score is None
    acquire.assert_not_called()


def test_close_failure_preserves_completed_grade_and_attempts_once():
    owned = session()
    owned.close.side_effect = RuntimeError("cleanup error")
    pipeline = build_pipeline(definition=definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "setup", "command": "prepare"}]}}}),
        capabilities=HostCapabilities(execution=lambda language: owned))
    assert pipeline.run(submission()).outcome.status == "completed"
    owned.close.assert_called_once()


@pytest.mark.parametrize("failure", [None, "start_server", "wait_ready"])
def test_server_profile_owns_startup_readiness_requests_and_teardown(failure):
    owned = session()
    owned.make_request.return_value.status_code = 200
    owned.close.side_effect = owned.stop_server
    if failure:
        getattr(owned, failure).side_effect = RuntimeError("server details")
    value = definition(templates=["api"], evaluator="health_check", parameters={"endpoint": "/health"})
    pipeline = build_pipeline(definition=value,
        capabilities=HostCapabilities(server_execution=lambda language: owned))
    result = pipeline.run(submission()).outcome
    assert result.status == ("failed" if failure else "completed")
    owned.close.assert_called_once()
    owned.stop_server.assert_called_once()
    if failure:
        assert result.score is None
        owned.make_request.assert_not_called()
    else:
        assert result.score == 100
        operations = [call[0] for call in owned.mock_calls]
        assert operations.index("prepare_workdir") < operations.index("start_server")
        assert operations.index("start_server") < operations.index("wait_ready") < operations.index("make_request")
        assert operations.index("make_request") < operations.index("close")


def test_static_work_does_not_initialize_concrete_host_manager(monkeypatch):
    from execution_host.docker import DockerHost
    from sandbox_manager import remote_client
    initialize = Mock(side_effect=AssertionError("static work must stay offline"))
    monkeypatch.setattr(remote_client, "RemoteSandboxManager", initialize)
    host = DockerHost()
    assert build_pipeline(definition=definition(), capabilities=host.capabilities).run(submission()).outcome.status == "completed"
    host.close()
    initialize.assert_not_called()


def test_concrete_hosts_have_independent_managers_and_idempotent_shutdown(monkeypatch):
    from execution_host.docker import DockerHost
    from sandbox_manager import remote_client
    first_manager, second_manager = Mock(), Mock()
    initialize = Mock(side_effect=[first_manager, second_manager])
    monkeypatch.setattr(remote_client, "RemoteSandboxManager", initialize)
    first, second = DockerHost(api_url="http://one"), DockerHost(api_url="http://two")
    first_session, second_session = first.acquire(Language.PYTHON), second.acquire(Language.JAVA)
    first_session.close()
    second_session.close()
    first.close()
    first.close()
    second.close()
    first_manager.destroy_sandbox.assert_called_once_with(Language.PYTHON, first_manager.get_sandbox.return_value)
    second_manager.destroy_sandbox.assert_called_once_with(Language.JAVA, second_manager.get_sandbox.return_value)
    first_manager.shutdown.assert_called_once()
    second_manager.shutdown.assert_called_once()
