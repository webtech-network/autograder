"""Bounded PostgreSQL workers recover saved input and fence expired attempts."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update

from autograder.models.capabilities import ExecutionBudget, requirements_for
from autograder.models.contracts.definition import compile_snapshot
from autograder.models.language import Language
from autograder.services.assessment import EXECUTION_CAPABILITIES

from web.config.logging import get_logger
from web.database.models.submission import Submission, SubmissionStatus
from web.database.models.grading_attempt import GradingAttempt
from web.service.grading_service import GradingRequest, evaluate, failed_outcome
from web.service.outcome_delivery import (
    OutcomeDeliveryError, StaleAttemptError, read_receipt, store_receipt, publish_finalized,
)

logger = get_logger(__name__)


#: Beyond the session and provider deadlines: grading, feedback and handing the outcome back.
ATTEMPT_MARGIN_SECONDS = 60.0


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class AttemptClock:
    """One attempt's deadline, derived from the bound definition like the sandbox's lifetime.

    The deadline is the execution session's lifetime (``budget.session_seconds``)
    plus the provider's deadline for each AI call plus ``margin``. It is clocked
    from the session's grant, so waiting for sandbox capacity does not count:
    until the grant the bound is the host's capacity wait (PRF-01) on top. A
    definition without execution (static or AI-only) is clocked from the claim.
    """

    def __init__(self, request, capabilities, margin):
        from execution_host.docker import GRADING_CAPACITY_WAIT_SECONDS
        try:
            requirements = requirements_for(compile_snapshot(request.definition), Language(request.language))
            budget = requirements.budget
            needs_session = bool(requirements.capabilities & EXECUTION_CAPABILITIES)
        except Exception:  # pylint: disable=broad-exception-caught
            budget, needs_session = ExecutionBudget(), False  # the grading itself fails fast
        ai_seconds = 0.0
        if budget.ai_calls:
            ai_seconds = budget.ai_calls * (getattr(getattr(capabilities, "ai", None), "deadline_seconds", 0.0) or 0.0)
        self.rest = (budget.session_seconds if needs_session else 0.0) + ai_seconds + margin
        self.deadline = monotonic() + (GRADING_CAPACITY_WAIT_SECONDS if needs_session else 0.0) + self.rest

    def remaining(self) -> float:
        """Seconds until the deadline (negative once it passed)."""
        return self.deadline - monotonic()

    def watch(self, capabilities):
        """The same capabilities; a granted session restarts the clock (thread-safe: one assignment)."""
        if capabilities is None:
            return None

        def clocked(acquire):
            if acquire is None:
                return None

            def acquire_and_clock(language, budget):
                session = acquire(language, budget)
                self.deadline = monotonic() + self.rest
                return session
            return acquire_and_clock
        return replace(capabilities, execution=clocked(capabilities.execution),
                       server_execution=clocked(capabilities.server_execution))


def _discard_late(task):
    """A grading abandoned at its deadline may still finish; its result is never published."""
    if task.cancelled():
        return
    if task.exception() is not None:
        logger.warning("A grading abandoned at its attempt deadline later failed: %r", task.exception())
    else:
        logger.warning("A grading abandoned at its attempt deadline finished late; its outcome is discarded")


class DurableWorker:
    """A process owns bounded workers; PostgreSQL owns the durable work state."""
    def __init__(self, session_factory, settings, capabilities=None, *, evaluator=evaluate,
                 attempt_margin=ATTEMPT_MARGIN_SECONDS):
        self.sessions = session_factory
        self.settings = settings
        self.capabilities = capabilities
        self.evaluator = evaluator
        self.attempt_margin = attempt_margin
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

    async def heartbeat(self, submission_id, attempt_id, finished, clock=None):
        while not finished.is_set():
            try:
                await asyncio.wait_for(finished.wait(), timeout=self.settings.LEASE_SECONDS / 3)
                return
            except asyncio.TimeoutError:
                pass
            if clock is not None and clock.remaining() <= 0:
                return  # An attempt past its deadline never renews its lease.
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
        clock = AttemptClock(request, self.capabilities, self.attempt_margin)
        finished = asyncio.Event()
        renewer = asyncio.create_task(self.heartbeat(request.submission_id, attempt_id, finished, clock))
        cancelled = False
        try:
            evaluation = asyncio.create_task(self.evaluator(request, clock.watch(self.capabilities)))
            while not evaluation.done() and clock.remaining() > 0:
                try:
                    # Short waits: a session grant moves the deadline.
                    await asyncio.wait({evaluation}, timeout=min(clock.remaining(), self.settings.LEASE_SECONDS / 3))
                except asyncio.CancelledError:
                    # Cancellation of a wrapper does not stop a grading thread. Keep its
                    # lease and providers alive and drain it, up to its deadline.
                    cancelled = True
            if evaluation.done():
                outcome = evaluation.result()
            else:
                # Its sandbox has already stopped itself; the thread cannot be stopped from here.
                logger.error("Grading attempt %s of submission %s passed its deadline", attempt_id,
                             request.submission_id)
                evaluation.add_done_callback(_discard_late)
                outcome = failed_outcome(request, "ATTEMPT_DEADLINE_EXCEEDED",
                                         "The grading attempt did not finish within its deadline.",
                                         category="capability", retryable=True)
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
