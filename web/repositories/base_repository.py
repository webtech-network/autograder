"""Base repository pattern for database operations."""

from typing import Generic, TypeVar, Type, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository providing common CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository.
        
        Args:
            model: The SQLAlchemy model class
            session: The async database session
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        """Create a new entity."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update entity by ID."""
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
            await self.session.refresh(instance)
        return instance
