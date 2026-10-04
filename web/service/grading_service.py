"""Run a bound definition and persist the engine's finalized shared outcome."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from time import monotonic
from autograder.autograder import build_pipeline
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.contracts.outcome import validate_outcome
from autograder.models.dataclass.submission import (
    EvaluationScope,
    Submission as AutograderSubmission,
    SubmissionFile,
)
from sandbox_manager.models.sandbox_models import Language
from web.config.logging import get_logger
from web.database import get_session
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
from web.repositories import SubmissionRepository, ResultRepository

logger = get_logger(__name__)


@dataclass
class GradingRequest:
    submission_id: int
    grading_config_id: int
    definition: dict
    configuration_version: int
    definition_hash: str
    language: str
    username: str
    external_user_id: str
    submission_files: dict
    locale: str = "en"
    evaluation_scope: dict | None = None

    @property
    def provenance(self):
        return DefinitionProvenance(
            definition_hash=self.definition_hash,
            reference=str(self.grading_config_id),
            revision=self.configuration_version,
        )


async def _run_pipeline(request):
    pipeline = build_pipeline(
        definition=request.definition,
        locale=request.locale,
        provenance=request.provenance,
    )
    files = {
        name: SubmissionFile(
            filename=f["filename"],
            content=f["content"],
            changed_lines=(
                set(f["changed_lines"]) if f.get("changed_lines") is not None else None
            ),
            metadata=f.get("file_metadata"),
        )
        for name, f in request.submission_files.items()
    }
    submission = AutograderSubmission(
        username=request.username,
        user_id=request.external_user_id,
        assignment_id=request.grading_config_id,
        submission_files=files,
        language=Language(request.language),
        locale=request.locale,
        evaluation_scope=(
            EvaluationScope(**request.evaluation_scope)
            if request.evaluation_scope
            else None
        ),
    )
    return await asyncio.to_thread(pipeline.run, submission)


async def persist_outcome(
    result_repo, submission_repo, submission_id, outcome, diagnostics=None
):
    normalized = validate_outcome(outcome).model_dump(mode="json")
    completed = normalized["status"] == "completed"
    await result_repo.create(
        submission_id=submission_id,
        outcome=normalized,
        diagnostics=diagnostics,
        final_score=normalized["score"],
        execution_time_ms=normalized["duration_ms"],
        pipeline_status=PipelineStatus.SUCCESS if completed else PipelineStatus.FAILED,
    )
    await submission_repo.update(
        submission_id,
        status=SubmissionStatus.COMPLETED if completed else SubmissionStatus.FAILED,
        graded_at=datetime.fromisoformat(
            normalized["finished_at"].replace("Z", "+00:00")
        ),
    )
    return normalized


async def grade_submission(request):
    async with get_session() as session:
        submissions, results = SubmissionRepository(session), ResultRepository(session)
        await submissions.update_status(
            request.submission_id, SubmissionStatus.PROCESSING
        )
        await session.commit()
        started = datetime.now(timezone.utc)
        started_monotonic = monotonic()
        try:
            execution = await _run_pipeline(request)
            if execution.outcome is None:
                raise RuntimeError("Engine returned no finalized outcome")
            finalized = execution.outcome.model_dump(mode="json")
        except Exception:
            # Roll back incomplete result writes before storing one safe terminal failure.
            await session.rollback()
            logger.exception("Grading failed for submission %s", request.submission_id)
            finished = datetime.now(timezone.utc)
            execution_id = str(uuid4())
            fallback = {
                "schema_version": "1.0",
                "status": "failed",
                "execution_id": execution_id,
                "language": request.language,
                "provenance": request.provenance.model_dump(mode="json"),
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_ms": max(0, int((monotonic() - started_monotonic) * 1000)),
                "score": None,
                "tree": None,
                "feedback": {"status": "disabled", "content": None, "error": None},
                "comparison": {"status": "disabled", "content": None, "error": None},
                "error": {
                    "code": "EXECUTION_FAILED",
                    "message": "Grading execution could not be completed.",
                    "category": "internal",
                    "retryable": True,
                    "correlation_id": execution_id,
                },
            }
            finalized = fallback
        # Persistence is adapter publication. Its failure cannot change a finalized grade.
        from web.service.outcome_delivery import publish_finalized

        await publish_finalized(
            session,
            request.submission_id,
            finalized,
            results=results,
            submissions=submissions,
        )
