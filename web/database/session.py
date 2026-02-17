"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from web.config.database import db_config
from web.database.base import Base

# Database URL from config (PostgreSQL only)
DATABASE_URL = db_config.url

# Create async engine with PostgreSQL connection pooling configuration
engine_kwargs = {
    "echo": db_config.echo,
    "future": True,
    "pool_size": db_config.pool_size,
    "max_overflow": db_config.max_overflow,
    "pool_timeout": db_config.pool_timeout,
    "pool_recycle": db_config.pool_recycle,
    "pool_pre_ping": True,  # Enable connection health checks
}

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Create session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
