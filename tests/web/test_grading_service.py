"""Grading persistence validates the finalized outcome rather than reserializing it."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest


@pytest.fixture(autouse=True)
def receipt_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_OUTCOME_RECEIPT_DIR", str(tmp_path))


from autograder.models.contracts.definition import compile_definition
from autograder.models.contracts.outcome import validate_outcome
from tests.web.test_contracts_v1 import definition, outcome
from web.service.grading_service import GradingRequest, grade_submission, _run_pipeline


def request():
    compiled = compile_definition(definition())
    return GradingRequest(
        submission_id=1,
        grading_config_id=1,
        definition=compiled.definition.model_dump(mode="json"),
        configuration_version=1,
        definition_hash=compiled.definition_hash,
        language="python",
        username="student",
        external_user_id="student",
        submission_files={
            "main.py": {
                "filename": "main.py",
                "content": "print('Hello')",
                "changed_lines": [1],
                "file_metadata": {"opaque": True},
            }
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_persists_shared_outcome_without_failed_zero(failed):
    bound = request()
    final = validate_outcome(
        outcome(
            {"id": 1, "version": 1, "definition_hash": bound.definition_hash},
            failed=failed,
            score=100,
        )
    )
    session = AsyncMock()
    submissions, results = AsyncMock(), AsyncMock()
    results.get_by_submission_id.return_value = None
    with patch("web.service.grading_service.get_session") as sessions, patch(
        "web.service.grading_service.SubmissionRepository", return_value=submissions
    ), patch(
        "web.service.grading_service.ResultRepository", return_value=results
    ), patch(
        "web.service.grading_service._run_pipeline",
        return_value=SimpleNamespace(outcome=final),
    ):
        sessions.return_value.__aenter__.return_value = session
        await grade_submission(bound)
    values = results.create.call_args.kwargs
    assert values["outcome"] == final.model_dump(mode="json")
    assert values["final_score"] == (None if failed else 100)
    assert submissions.update.call_args.kwargs["status"].value == (
        "failed" if failed else "completed"
    )


@pytest.mark.asyncio
async def test_exception_rolls_back_and_exposes_safe_terminal_error():
    bound = request()
    session, submissions, results = AsyncMock(), AsyncMock(), AsyncMock()
    results.get_by_submission_id.return_value = None
    with patch("web.service.grading_service.get_session") as sessions, patch(
        "web.service.grading_service.SubmissionRepository", return_value=submissions
    ), patch(
        "web.service.grading_service.ResultRepository", return_value=results
    ), patch(
        "web.service.grading_service._run_pipeline",
        side_effect=RuntimeError("secret provider token"),
    ):
        sessions.return_value.__aenter__.return_value = session
        await grade_submission(bound)
    assert session.rollback.await_count == 1
    stored = results.create.call_args.kwargs
    assert stored["final_score"] is None
    assert stored["outcome"]["error"]["code"] == "EXECUTION_FAILED"
    assert "secret" not in str(stored["outcome"])


@pytest.mark.asyncio
async def test_run_pipeline_hydrates_evaluation_context():
    bound = request()
    bound.evaluation_scope = {"scoped_files": ["main.py"]}
    pipeline = Mock()
    with patch(
        "web.service.grading_service.build_pipeline", return_value=pipeline
    ) as build:
        await _run_pipeline(bound)
    submission = pipeline.run.call_args.args[0]
    assert submission.submission_files["main.py"].changed_lines == {1}
    assert submission.submission_files["main.py"].metadata == {"opaque": True}
    assert submission.evaluation_scope.scoped_files == ["main.py"]
    assert build.call_args.kwargs["definition"] == bound.definition
    assert build.call_args.kwargs["provenance"].revision == 1


@pytest.mark.asyncio
async def test_receipt_retains_completed_grade_and_retry_never_regrades(
    test_client, tmp_path
):
    import json
    from tests.web.test_contracts_v1 import create
    from web.service.outcome_delivery import (
        OutcomeDeliveryError,
        republish_receipt,
        write_receipt,
    )
    from web.repositories import ResultRepository

    config = await create(test_client)
    payload = {
        "external_assignment_id": "assignment",
        "external_user_id": "student",
        "username": "Student",
        "files": [{"filename": "main.py", "content": "print('Hello')"}],
    }
    with patch(
        "web.api.v1.submissions.grade_submission", new_callable=AsyncMock
    ) as scheduled:
        response = await test_client.post("/api/v1/submissions", json=payload)
        import asyncio

        await asyncio.sleep(0)
        bound = scheduled.call_args.args[0]
    finalized = validate_outcome(outcome(config, score=100))
    with patch(
        "web.service.grading_service._run_pipeline",
        return_value=SimpleNamespace(outcome=finalized),
    ) as engine, patch.object(
        ResultRepository, "create", side_effect=RuntimeError("database unavailable")
    ):
        with pytest.raises(OutcomeDeliveryError) as failure:
            await grade_submission(bound)
    path = failure.value.receipt_path
    receipt = json.loads(path.read_text())
    assert path.stat().st_mode & 0o777 == 0o600
    assert receipt["outcome"] == finalized.model_dump(mode="json")
    assert (
        receipt["outcome"]["provenance"]["definition_hash"] == config["definition_hash"]
    )
    assert (
        await test_client.get(f'/api/v1/submissions/{response.json()["id"]}')
    ).json()["status"] == "processing"
    with patch(
        "web.service.grading_service._run_pipeline",
        side_effect=AssertionError("retry must not grade"),
    ):
        await republish_receipt(path)
        # A commit-acknowledgement ambiguity can leave an already persisted receipt.
        duplicate = write_receipt(bound.submission_id, finalized)
        await republish_receipt(duplicate)
    engine.assert_awaited_once()
    assert not path.exists() and not duplicate.exists()
    poll = (await test_client.get(f"/api/v1/submissions/{bound.submission_id}")).json()
    assert poll["status"] == "completed" and poll["final_score"] == 100
    assert poll["provenance"] == finalized.provenance.model_dump(mode="json")
