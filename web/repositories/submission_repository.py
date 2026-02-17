"""Submission repository."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from web.database.models.submission import Submission, SubmissionStatus
from web.repositories.base_repository import BaseRepository


class SubmissionRepository(BaseRepository[Submission]):
    """Repository for Submission operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Submission, session)

    async def create(
            self,
            grading_config_id: int,
            external_user_id: str,
            username: str,
            submission_files: dict,  # Receives Dict[str, str] from API
            language: Optional[str] = None,
            status: SubmissionStatus = SubmissionStatus.PENDING,
            submission_metadata: Optional[dict] = None,
    ) -> Submission:
        """Create a new submission."""

        # submission_files is already Dict[str, str] - store as-is
        db_submission = Submission(
            grading_config_id=grading_config_id,
            external_user_id=external_user_id,
            username=username,
            submission_files=submission_files,  # Store directly
            language=language,
            status=status,
            submission_metadata=submission_metadata,
        )

        self.session.add(db_submission)
        return db_submission

    async def get_by_id_with_result(self, id: int) -> Optional[Submission]:
        """Get submission by ID with result loaded."""
        result = await self.session.execute(
            select(Submission)
            .options(joinedload(Submission.result))
            .where(Submission.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self, external_user_id: str, limit: int = 100, offset: int = 0
    ) -> List[Submission]:
        """Get all submissions by user."""
        result = await self.session.execute(
            select(Submission)
            .where(Submission.external_user_id == external_user_id)
            .order_by(Submission.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_config(
        self, grading_config_id: int, limit: int = 100, offset: int = 0
    ) -> List[Submission]:
        """Get all submissions for a grading configuration."""
        result = await self.session.execute(
            select(Submission)
            .where(Submission.grading_config_id == grading_config_id)
            .order_by(Submission.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_status(
        self, status: SubmissionStatus, limit: int = 100, offset: int = 0
    ) -> List[Submission]:
        """Get all submissions with a specific status."""
        result = await self.session.execute(
            select(Submission)
            .where(Submission.status == status)
            .order_by(Submission.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(self, id: int, status: SubmissionStatus) -> Optional[Submission]:
        """Update submission status."""
        return await self.update(id, status=status)
