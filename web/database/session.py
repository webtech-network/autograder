"""Database session management."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from web.config.database import db_config
from web.database.base import Base

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./autograder.db")

# Create async engine with proper pooling configuration
# Use NullPool for SQLite (no connection pooling needed)
# Use default QueuePool for PostgreSQL with configured pool size
engine_kwargs = {
    "echo": os.getenv("DATABASE_ECHO", "False").lower() == "true",
    "future": True,
}

if db_config.is_sqlite:
    # SQLite doesn't support connection pooling effectively
    engine_kwargs["poolclass"] = NullPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling configuration
    engine_kwargs["pool_size"] = db_config.pool_size
    engine_kwargs["max_overflow"] = db_config.max_overflow
    engine_kwargs["pool_timeout"] = db_config.pool_timeout
    engine_kwargs["pool_recycle"] = db_config.pool_recycle
    engine_kwargs["pool_pre_ping"] = True  # Enable connection health checks

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
