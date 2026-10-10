"""Database construction and sessions with explicit transaction owners."""
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from web.database.base import Base


def create_database(url, *, echo=False, pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=3600):
    options = {"echo": echo, "pool_pre_ping": True}
    if not url.startswith("sqlite"):
        options.update(pool_size=pool_size, max_overflow=max_overflow,
                       pool_timeout=pool_timeout, pool_recycle=pool_recycle)
    engine = create_async_engine(url, **options)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session(session_factory):
    """Closing rolls back unfinished transactions; operations explicitly commit."""
    async with session_factory() as session:
        yield session
