"""Application lifespan uses only the host attached to this application."""
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    host = app.state.host
    try:
        await host.start()
        yield
    finally:
        await host.close()
