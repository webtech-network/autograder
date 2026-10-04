"""Identity lookup and atomic optimistic updates for configuration resources."""

from datetime import datetime, timezone
from sqlalchemy import select, update
from web.database.models.grading_config import GradingConfiguration
from web.repositories.base_repository import BaseRepository


class GradingConfigRepository(BaseRepository[GradingConfiguration]):
    def __init__(self, session):
        super().__init__(GradingConfiguration, session)

    async def get_by_external_id(self, external_assignment_id):
        result = await self.session.execute(
            select(GradingConfiguration).where(
                GradingConfiguration.external_assignment_id == external_assignment_id
            )
        )
        return result.scalar_one_or_none()

    async def get_active_configs(self, limit=100, offset=0):
        result = await self.session.execute(
            select(GradingConfiguration)
            .where(GradingConfiguration.is_active.is_(True))
            .order_by(GradingConfiguration.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def conditional_update(self, config_id, expected_version, changes):
        # Even no-op updates must check the precondition atomically.
        values = dict(changes)
        if changes:
            values.update(
                version=expected_version + 1, updated_at=datetime.now(timezone.utc)
            )
        else:
            values["version"] = expected_version
        result = await self.session.execute(
            update(GradingConfiguration)
            .where(
                GradingConfiguration.id == config_id,
                GradingConfiguration.version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        await self.session.flush()
        config = await self.get_by_id(config_id)
        await self.session.refresh(config)
        return config
