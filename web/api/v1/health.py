"""Health and readiness check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from fastapi.responses import JSONResponse

from web.config.logging import get_logger
from web.api.deps import get_host


logger = get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@router.get("/ready")
async def readiness_check(host=Depends(get_host)):
    """Readiness check for orchestration platforms."""
    try:
        async with host.sessions() as session:
            await session.execute(text("SELECT 1"))
        ready = host.ready
    except Exception:
        ready = False
    status_code = 200 if ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "durable_acceptance": ready,
            "execution_providers": "checked when required",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

