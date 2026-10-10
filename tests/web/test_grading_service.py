"""Evaluation returns finalized artifacts; delivery owns persistence and replay."""
import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from autograder.models.contracts.definition import compile_definition
from autograder.models.contracts.outcome import validate_outcome
from tests.web.test_contracts_v1 import definition, outcome, create
from web.database.models.submission import Submission
from web.repositories import ResultRepository
from web.service.grading_service import GradingRequest, evaluate, _run_pipeline
from web.service.outcome_delivery import OutcomeDeliveryError, publish_finalized, republish_receipt, write_receipt


def request():
    compiled = compile_definition(definition())
    return GradingRequest(submission_id=1, grading_config_id=1,
                          definition=compiled.definition.model_dump(mode="json"), configuration_version=1,
                          definition_hash=compiled.definition_hash, language="python", username="student",
                          external_user_id="student", submission_files={"main.py": {
                              "filename": "main.py", "content": "print('Hello')", "changed_lines": [1],
                              "file_metadata": {"opaque": True}}})


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_evaluate_returns_shared_artifact_without_failed_zero(failed):
    bound = request()
    final = validate_outcome(outcome({"id": 1, "version": 1, "definition_hash": bound.definition_hash},
                                     failed=failed, score=100))
    with patch("web.service.grading_service._run_pipeline", return_value=SimpleNamespace(outcome=final)):
        assert await evaluate(bound) == final.model_dump(mode="json")


@pytest.mark.asyncio
async def test_exception_exposes_safe_terminal_error():
    with patch("web.service.grading_service._run_pipeline", side_effect=RuntimeError("secret provider token")):
        stored = await evaluate(request())
    assert stored["score"] is None
    assert stored["error"]["code"] == "EXECUTION_FAILED"
    assert "secret" not in str(stored)
    validate_outcome(stored)


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_lines", [None, []])
async def test_run_pipeline_hydrates_context_and_preserves_absent_vs_empty(changed_lines):
    bound = request()
    bound.submission_files["main.py"]["changed_lines"] = changed_lines
    bound = replace(bound, evaluation_scope={"scoped_files": ["main.py"]}, locale="pt-br")
    pipeline, capabilities = Mock(), Mock()
    with patch("web.service.grading_service.build_pipeline", return_value=pipeline) as build:
        await _run_pipeline(bound, capabilities)
    submission = pipeline.run.call_args.args[0]
    assert submission.submission_files["main.py"].changed_lines == (None if changed_lines is None else set())
    assert submission.submission_files["main.py"].metadata == {"opaque": True}
    assert submission.evaluation_scope.scoped_files == ["main.py"]
    assert submission.locale == "pt-br"
    assert build.call_args.kwargs["capabilities"] is capabilities
    assert build.call_args.kwargs["provenance"].revision == 1


@pytest.mark.asyncio
async def test_receipt_retains_completed_grade_and_retry_never_regrades(test_client, application):
    config = await create(test_client)
    response = await test_client.post("/api/v1/submissions", json={
        "external_assignment_id": "assignment", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "main.py", "content": "print('Hello')"}]})
    assert response.status_code == 202
    host = application.state.host
    bound, attempt_id = await host.worker.claim()
    finalized = validate_outcome(outcome(config, score=100))
    with patch.object(ResultRepository, "create", side_effect=RuntimeError("database unavailable")):
        with pytest.raises(OutcomeDeliveryError) as failure:
            await publish_finalized(host.sessions, bound.submission_id, finalized,
                                    directory=host.settings.RECEIPT_DIR, attempt_id=attempt_id)
    path = failure.value.receipt_path
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["outcome"] == finalized.model_dump(mode="json")
    with patch("web.service.grading_service._run_pipeline", side_effect=AssertionError("retry must not grade")):
        await republish_receipt(path, host.sessions)
        duplicate = write_receipt(bound.submission_id, finalized, directory=host.settings.RECEIPT_DIR, attempt_id=attempt_id)
        await republish_receipt(duplicate, host.sessions)
    assert not path.exists() and not duplicate.exists()
    poll = (await test_client.get(f"/api/v1/submissions/{bound.submission_id}")).json()
    assert poll["status"] == "completed" and poll["final_score"] == 100
    assert poll["provenance"] == finalized.provenance.model_dump(mode="json")
