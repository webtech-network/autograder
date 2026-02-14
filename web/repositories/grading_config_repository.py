"""GradingConfiguration repository."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.database.models.grading_config import GradingConfiguration
from web.repositories.base_repository import BaseRepository


class GradingConfigRepository(BaseRepository[GradingConfiguration]):
    """Repository for GradingConfiguration operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(GradingConfiguration, session)

    async def get_by_external_id(self, external_assignment_id: str) -> Optional[GradingConfiguration]:
        """Get grading configuration by external assignment ID."""
        result = await self.session.execute(
            select(GradingConfiguration).where(
                GradingConfiguration.external_assignment_id == external_assignment_id,
                GradingConfiguration.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_active_configs(self, limit: int = 100, offset: int = 0):
        """Get all active grading configurations."""
        result = await self.session.execute(
            select(GradingConfiguration)
            .where(GradingConfiguration.is_active == True)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
