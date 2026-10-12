"""Retain finalized outcomes, then publish with attempt ownership and one commit."""
import argparse
import asyncio
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from autograder.models.contracts.outcome import TerminalOutcome, validate_outcome
from web.database.models.submission import Submission, SubmissionStatus
from web.database.models.grading_attempt import GradingAttempt
from web.database.models.submission_result import PipelineStatus
from web.repositories import ResultRepository, SubmissionRepository


class OutcomeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: int = Field(gt=0, strict=True)
    attempt_id: str | None = None
    outcome: TerminalOutcome


class OutcomeDeliveryError(RuntimeError):
    def __init__(self, receipt_path):
        self.receipt_path = Path(receipt_path)
        super().__init__(f"Finalized outcome publication failed; retry receipt {self.receipt_path}")


class StaleAttemptError(ValueError):
    """A newer worker owns this submission; the old attempt cannot publish."""


async def persist_outcome(result_repo, submission_repo, submission_id, outcome, diagnostics=None):
    """Write the authoritative artifact; caller owns commit/rollback."""
    normalized = validate_outcome(outcome).model_dump(mode="json")
    completed = normalized["status"] == "completed"
    await result_repo.create(submission_id=submission_id, outcome=normalized, diagnostics=diagnostics,
                             final_score=normalized["score"], execution_time_ms=normalized["duration_ms"],
                             pipeline_status=PipelineStatus.SUCCESS if completed else PipelineStatus.FAILED)
    await submission_repo.update(submission_id,
                                 status=SubmissionStatus.COMPLETED if completed else SubmissionStatus.FAILED,
                                 graded_at=datetime.fromisoformat(normalized["finished_at"].replace("Z", "+00:00")),
                                 lease_until=None)
    return normalized


def write_receipt(submission_id, outcome, *, directory=None, attempt_id=None):
    receipt = OutcomeReceipt(submission_id=submission_id, outcome=outcome, attempt_id=attempt_id)
    directory = Path(directory or os.getenv("WEB_OUTCOME_RECEIPT_DIR", "data/unpublished-outcomes"))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    suffix = hashlib.sha256(receipt.outcome.execution_id.encode()).hexdigest()[:16]
    target = directory / f"submission-{submission_id}-{suffix}.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".receipt-", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(receipt.model_dump_json())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def read_receipt(path):
    return OutcomeReceipt.model_validate_json(Path(path).read_text(encoding="utf-8"))


def check_receipt(row, receipt):
    provenance = receipt.outcome.provenance
    if (provenance.definition_hash != row.definition_hash
            or provenance.reference != str(row.grading_config_id)
            or provenance.revision != row.configuration_version
            or receipt.outcome.language != row.language):
        raise ValueError("Receipt provenance does not match its bound submission")
    if receipt.attempt_id is not None and row.attempt_id != receipt.attempt_id:
        raise StaleAttemptError("A newer attempt owns this submission")
    if receipt.attempt_id is None and row.attempt_id is not None:
        raise StaleAttemptError("A worker publication requires its attempt identity")


async def store_receipt(session, receipt, *, row=None):
    """Row locking serializes attempt publication and retry after commit ambiguity."""
    if row is None:
        row = await session.scalar(select(Submission).where(Submission.id == receipt.submission_id).with_for_update())
    if row is None:
        raise ValueError("Receipt submission does not exist")
    check_receipt(row, receipt)
    results = ResultRepository(session)
    existing = await results.get_by_submission_id(receipt.submission_id)
    normalized = receipt.outcome.model_dump(mode="json")
    if existing:
        if existing.outcome != normalized:
            raise StaleAttemptError("A different outcome already exists for this submission")
    else:
        await persist_outcome(results, SubmissionRepository(session), receipt.submission_id, normalized)
    if receipt.attempt_id:
        attempt = await session.get(GradingAttempt, receipt.attempt_id)
        if attempt:
            attempt.status = "published"
            attempt.finished_at = datetime.now(timezone.utc)


async def publish_finalized(session_factory, submission_id, outcome, *, directory=None, attempt_id=None):
    path = await asyncio.to_thread(write_receipt, submission_id, outcome, directory=directory, attempt_id=attempt_id)
    try:
        await republish_receipt(path, session_factory)
    except StaleAttemptError:
        # A fenced receipt is audit evidence, never a new grading request.
        raise
    except Exception as exc:
        raise OutcomeDeliveryError(path) from exc
    return path


async def republish_receipt(path, session_factory):
    """Replay an artifact without importing or constructing a grading pipeline."""
    path = Path(path)
    receipt = read_receipt(path)
    async with session_factory() as session:
        try:
            await store_receipt(session, receipt)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    path.unlink(missing_ok=True)


def main():
    from web.core.config import Settings
    from web.database.session import create_database

    parser = argparse.ArgumentParser(description="Publish a saved finalized outcome without regrading")
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()

    async def replay():
        engine, sessions = create_database(Settings().DATABASE_URL)
        try:
            await republish_receipt(args.receipt, sessions)
        finally:
            await engine.dispose()

    asyncio.run(replay())


if __name__ == "__main__":
    main()
