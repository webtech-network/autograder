"""SubmissionResult repository."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.database.models.submission_result import SubmissionResult
from web.repositories.base_repository import BaseRepository


class ResultRepository(BaseRepository[SubmissionResult]):
    """Repository for SubmissionResult operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(SubmissionResult, session)

    async def get_by_submission_id(self, submission_id: int) -> Optional[SubmissionResult]:
        """Get result by submission ID."""
        result = await self.session.execute(
            select(SubmissionResult).where(SubmissionResult.submission_id == submission_id)
        )
        return result.scalar_one_or_none()
