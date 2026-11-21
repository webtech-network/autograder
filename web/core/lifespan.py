"""Application lifespan uses only the host attached to this application."""
from contextlib import asynccontextmanager

from web.config.tracing import shutdown_api_tracing


@asynccontextmanager
async def lifespan(app):
    host = app.state.host
    try:
        await host.start()
        yield
    finally:
        await host.close()
        # After the workers drained: their last attempts' spans are exported too.
        shutdown_api_tracing()
