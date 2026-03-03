"""API router aggregation."""

from fastapi import APIRouter

from web.api.v1 import api_router as v1_router


# Create the main API router with /api/v1 prefix
api_router = APIRouter()

# Include v1 routes under /api/v1
api_router.include_router(v1_router, prefix="/api/v1")


