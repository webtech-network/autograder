"""Bounded PostgreSQL workers recover saved input and fence expired attempts."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update

from web.config.logging import get_logger
from web.database.models.submission import Submission, SubmissionStatus
from web.database.models.grading_attempt import GradingAttempt
from web.service.grading_service import GradingRequest, evaluate, failed_outcome
from web.service.outcome_delivery import (
    OutcomeDeliveryError, StaleAttemptError, read_receipt, store_receipt, publish_finalized,
)

logger = get_logger(__name__)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class DurableWorker:
    """A process owns bounded workers; PostgreSQL owns the durable work state."""
    def __init__(self, session_factory, settings, capabilities=None, *, evaluator=evaluate):
        self.sessions = session_factory
        self.settings = settings
        self.capabilities = capabilities
        self.evaluator = evaluator
        self.tasks = set()
        self.stopping = asyncio.Event()

    async def claim(self):
        async with self.sessions() as session:
            try:
                now = utc(await session.scalar(select(func.now())))
                row = await session.scalar(
                    select(Submission).where(
                        Submission.definition_snapshot.is_not(None),
                        or_(Submission.status == SubmissionStatus.PENDING,
                            and_(Submission.status == SubmissionStatus.PROCESSING,
                                 or_(Submission.lease_until <= now, Submission.lease_until.is_(None)))),
                    ).order_by(Submission.id).with_for_update(skip_locked=True).limit(1)
                )
                if row is None:
                    return None
                # A retained grade precedes a new attempt, including commit-ack ambiguity.
                for path in sorted(Path(self.settings.RECEIPT_DIR).glob(f"submission-{row.id}-*.json")):
                    try:
                        receipt = read_receipt(path)
                    except (ValueError, OSError):
                        logger.exception("Unreadable recovery receipt: %s", path)
                        path.rename(path.with_suffix(".invalid"))
                        continue
                    if receipt.attempt_id == row.attempt_id:
                        await store_receipt(session, receipt, row=row)
                        await session.commit()
                        path.unlink(missing_ok=True)
                        return None
                request = GradingRequest.from_row(row)
                if row.attempt_id:
                    previous = await session.get(GradingAttempt, row.attempt_id)
                    if previous:
                        previous.status = "expired"
                        previous.finished_at = now
                if row.attempt_count >= self.settings.MAX_ATTEMPTS:
                    # This is a recovery failure, not an assessed student zero.
                    from web.service.outcome_delivery import persist_outcome
                    from web.repositories import ResultRepository, SubmissionRepository
                    await persist_outcome(ResultRepository(session), SubmissionRepository(session), row.id,
                                          failed_outcome(request, "RECOVERY_EXHAUSTED", "Grading recovery attempts were exhausted."))
                    await session.commit()
                    return None
                row.attempt_id = str(uuid4())
                row.attempt_count += 1
                row.status = SubmissionStatus.PROCESSING
                row.lease_until = now + timedelta(seconds=self.settings.LEASE_SECONDS)
                session.add(GradingAttempt(id=row.attempt_id, submission_id=row.id, number=row.attempt_count))
                attempt_id = row.attempt_id
                await session.commit()
                return request, attempt_id
            except Exception:
                await session.rollback()
                raise

    async def heartbeat(self, submission_id, attempt_id, finished):
        while not finished.is_set():
            try:
                await asyncio.wait_for(finished.wait(), timeout=self.settings.LEASE_SECONDS / 3)
                return
            except asyncio.TimeoutError:
                pass
            try:
                async with self.sessions() as session:
                    now = utc(await session.scalar(select(func.now())))
                    changed = await session.execute(
                        update(Submission).where(Submission.id == submission_id,
                                                 Submission.attempt_id == attempt_id,
                                                 Submission.status == SubmissionStatus.PROCESSING)
                        .values(lease_until=now + timedelta(seconds=self.settings.LEASE_SECONDS))
                    )
                    await session.commit()
                    if not changed.rowcount:
                        return
            except Exception:
                # Losing the database never proves the grading thread has stopped.
                logger.exception("Worker lease renewal failed for submission %s", submission_id)

    async def run_once(self):
        claimed = await self.claim()
        if claimed is None:
            return False
        request, attempt_id = claimed
        finished = asyncio.Event()
        renewer = asyncio.create_task(self.heartbeat(request.submission_id, attempt_id, finished))
        cancelled = False
        try:
            evaluation = asyncio.create_task(self.evaluator(request, self.capabilities))
            try:
                outcome = await asyncio.shield(evaluation)
            except asyncio.CancelledError:
                # Cancellation of a wrapper does not stop a grading thread. Keep
                # its lease and providers alive, drain it and retain its outcome.
                cancelled = True
                outcome = await evaluation
            await publish_finalized(self.sessions, request.submission_id, outcome,
                                    directory=self.settings.RECEIPT_DIR, attempt_id=attempt_id)
        except StaleAttemptError:
            logger.warning("Discarding publication ownership for stale attempt %s", attempt_id)
        except OutcomeDeliveryError:
            logger.exception("Finalized outcome retained for submission %s", request.submission_id)
        finally:
            finished.set()
            await renewer
        if cancelled:
            raise asyncio.CancelledError
        return True

    async def run(self):
        while not self.stopping.is_set():
            try:
                if await self.run_once():
                    continue
            except Exception:
                logger.exception("Durable grading worker could not claim or execute work")
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=self.settings.POLL_SECONDS)
            except asyncio.TimeoutError:
                pass

    def start(self):
        if self.tasks:
            raise RuntimeError("Worker already started")
        self.stopping.clear()
        for _ in range(self.settings.WORKER_COUNT):
            task = asyncio.create_task(self.run())
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def stop(self):
        """Stop claiming, drain owned threads and cleanup, then permit host disposal."""
        self.stopping.set()
        if self.tasks:
            draining = asyncio.gather(*self.tasks)
            try:
                await asyncio.shield(draining)
            except asyncio.CancelledError:
                await draining
                raise
