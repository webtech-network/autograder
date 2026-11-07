"""Drive a durable worker to quiescence, including the retries of retryable failures."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from web.database.models.submission import Submission, SubmissionStatus


async def end_retry_backoffs(sessions):
    """Make every released submission (processing, no owning attempt) claimable now; return how many."""
    async with sessions() as session:
        changed = await session.execute(
            update(Submission).where(Submission.status == SubmissionStatus.PROCESSING, Submission.attempt_id.is_(None))
            .values(lease_until=datetime.now(timezone.utc) - timedelta(seconds=10)))
        await session.commit()
        return changed.rowcount


async def drain(worker, sessions):
    """Run attempts until nothing is claimable, ending each retry backoff instead of waiting for it."""
    while await worker.run_once() or await end_retry_backoffs(sessions):
        pass
