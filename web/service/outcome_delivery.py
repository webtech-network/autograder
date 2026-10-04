"""Local publication receipts: retain a finalized grade and replay it without grading."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
from pydantic import BaseModel, ConfigDict, Field
from autograder.models.contracts.outcome import TerminalOutcome
from web.config.logging import get_logger
from web.database import get_session
from web.repositories import ResultRepository, SubmissionRepository

logger = get_logger(__name__)


class OutcomeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: int = Field(gt=0, strict=True)
    outcome: TerminalOutcome


class OutcomeDeliveryError(RuntimeError):
    """Publication failed; receipt_path retains the authoritative finalized outcome."""

    def __init__(self, receipt_path):
        self.receipt_path = Path(receipt_path)
        super().__init__(
            f"Finalized outcome publication failed; retry receipt {self.receipt_path}"
        )


def write_receipt(submission_id, outcome):
    receipt = OutcomeReceipt(submission_id=submission_id, outcome=outcome)
    directory = Path(os.getenv("WEB_OUTCOME_RECEIPT_DIR", "data/unpublished-outcomes"))
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
        # Persist the rename before attempting database delivery.
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


async def publish_finalized(
    session, submission_id, outcome, *, results=None, submissions=None
):
    """Always save the artifact first; database errors cannot rewrite grading status."""
    path = await asyncio.to_thread(write_receipt, submission_id, outcome)
    try:
        await _persist_receipt(
            session,
            OutcomeReceipt(submission_id=submission_id, outcome=outcome),
            results=results,
            submissions=submissions,
        )
    except Exception as exc:
        await session.rollback()
        logger.error(
            "Finalized outcome retained for publication retry: receipt=%s", path
        )
        raise OutcomeDeliveryError(path) from exc
    path.unlink()


async def _persist_receipt(session, receipt, *, results=None, submissions=None):
    from web.service.grading_service import persist_outcome

    results = results if results is not None else ResultRepository(session)
    submissions = (
        submissions if submissions is not None else SubmissionRepository(session)
    )
    existing = await results.get_by_submission_id(receipt.submission_id)
    normalized = receipt.outcome.model_dump(mode="json")
    if existing:
        if existing.outcome != normalized:
            raise ValueError("A different outcome already exists for this submission")
    else:
        await persist_outcome(results, submissions, receipt.submission_id, normalized)
    await session.commit()


async def republish_receipt(path):
    """Explicit operational replay. Never builds a pipeline or provisions resources."""
    path = Path(path)
    receipt = OutcomeReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    async with get_session() as session:
        submission = await SubmissionRepository(session).get_by_id(
            receipt.submission_id
        )
        if submission is None:
            raise ValueError("Receipt submission does not exist")
        provenance = receipt.outcome.provenance
        if (
            provenance.definition_hash != submission.definition_hash
            or provenance.reference != str(submission.grading_config_id)
            or provenance.revision != submission.configuration_version
            or receipt.outcome.language != submission.language
        ):
            raise ValueError("Receipt provenance does not match its bound submission")
        try:
            await _persist_receipt(session, receipt)
        except Exception as exc:
            logger.error("Outcome retry failed; receipt retained: receipt=%s", path)
            raise OutcomeDeliveryError(path) from exc
    path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Publish a saved finalized outcome without regrading"
    )
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    asyncio.run(republish_receipt(args.receipt))


if __name__ == "__main__":
    main()
