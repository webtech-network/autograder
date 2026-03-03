"""API v1 routes."""

from fastapi import APIRouter

from web.api.v1 import health, templates, configs, submissions


# Create the main v1 router
api_router = APIRouter()

# Include health endpoints (no prefix, at root level)
api_router.include_router(health.router)

# Include all other v1 endpoints
api_router.include_router(templates.router)
api_router.include_router(configs.router)
api_router.include_router(submissions.router)

