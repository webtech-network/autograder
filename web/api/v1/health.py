"""Health and readiness check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web.core.lifespan import get_template_service


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check for orchestration platforms."""
    template_service = get_template_service()

    ready = template_service is not None
    status_code = 200 if ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

