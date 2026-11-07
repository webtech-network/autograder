"""Health and readiness check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from fastapi.responses import JSONResponse

from autograder import __version__
from web.config.logging import get_logger
from web.api.deps import configured_principals, get_host


logger = get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
    }


@router.get("/ready")
async def readiness_check(host=Depends(get_host)):
    """Readiness check for orchestration platforms."""
    try:
        async with host.sessions() as session:
            await session.execute(text("SELECT 1"))
        durable = host.ready
    except Exception:
        durable = False
    authentication = "configured" if configured_principals(host.settings) else "not_configured"
    ready = durable and authentication == "configured"
    status_code = 200 if ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "durable_acceptance": durable,
            "authentication": authentication,
            "execution_providers": "checked when required",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

