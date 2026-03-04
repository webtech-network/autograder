"""Template library endpoints."""

from fastapi import APIRouter, HTTPException

from web.core.lifespan import get_template_service


router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("")
async def list_templates():
    """List all available grading templates."""
    template_service = get_template_service()

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not initialized")

    templates = template_service.get_all_templates_info()
    return {"templates": templates}


@router.get("/{template_name}")
async def get_template_info(template_name: str):
    """Get information about a specific template."""
    template_service = get_template_service()

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not initialized")

    try:
        template_info = template_service.get_template_info(template_name)
        return template_info
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


