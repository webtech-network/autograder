"""Shared API dependencies."""

from sqlalchemy.ext.asyncio import AsyncSession

from web.database import get_session


async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    async with get_session() as session:
        yield session

