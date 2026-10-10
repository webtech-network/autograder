"""Evaluate saved input; persistence and worker scheduling belong to the host."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from autograder.autograder import build_pipeline
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.dataclass.submission import EvaluationScope, Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language
from web.config.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
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

    @classmethod
    def from_row(cls, row):
        return cls(
            submission_id=row.id, grading_config_id=row.grading_config_id,
            definition=row.definition_snapshot, configuration_version=row.configuration_version,
            definition_hash=row.definition_hash, language=row.language, username=row.username,
            external_user_id=row.external_user_id, submission_files=row.submission_files,
            locale=row.locale, evaluation_scope=row.evaluation_scope,
        )

    @property
    def provenance(self):
        return DefinitionProvenance(definition_hash=self.definition_hash,
                                    reference=str(self.grading_config_id), revision=self.configuration_version)


def failed_outcome(request, code="EXECUTION_FAILED", message="Grading execution could not be completed.", *, started=None, duration_ms=0):
    execution_id = str(uuid4())
    finished = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0", "status": "failed", "execution_id": execution_id,
        "language": request.language, "provenance": request.provenance.model_dump(mode="json"),
        "started_at": (started or finished).isoformat(), "finished_at": finished.isoformat(),
        "duration_ms": duration_ms, "score": None, "tree": None,
        "feedback": {"status": "disabled"}, "comparison": {"status": "disabled"},
        "error": {"code": code, "message": message, "category": "internal",
                  "retryable": False, "correlation_id": execution_id},
    }


async def _run_pipeline(request, capabilities=None):
    pipeline = build_pipeline(definition=request.definition, locale=request.locale,
                              provenance=request.provenance, capabilities=capabilities)
    files = {
        name: SubmissionFile(filename=value["filename"], content=value["content"],
                             changed_lines=set(value["changed_lines"]) if value.get("changed_lines") is not None else None,
                             metadata=value.get("file_metadata"))
        for name, value in request.submission_files.items()
    }
    submission = Submission(username=request.username, user_id=request.external_user_id,
                            assignment_id=request.grading_config_id, submission_files=files,
                            language=Language(request.language), locale=request.locale,
                            evaluation_scope=EvaluationScope(**request.evaluation_scope) if request.evaluation_scope is not None else None)
    # Cancellation of the caller cannot release resources still used by its thread.
    worker = asyncio.create_task(asyncio.to_thread(pipeline.run, submission))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await worker
        raise


async def evaluate(request, capabilities=None):
    started, tick = datetime.now(timezone.utc), monotonic()
    try:
        execution = await _run_pipeline(request, capabilities)
        if execution.outcome is None:
            raise RuntimeError("Engine returned no finalized outcome")
        return execution.outcome.model_dump(mode="json")
    except Exception:
        logger.exception("Grading failed for submission %s", request.submission_id)
        return failed_outcome(request, started=started, duration_ms=max(0, int((monotonic() - tick) * 1000)))
