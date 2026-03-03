"""Template library endpoints."""

        raise HTTPException(status_code=404, detail=str(e))
    except KeyError as e:
        return template_info
        template_info = template_service.get_template_info(template_name)
    try:

        raise HTTPException(status_code=503, detail="Template service not initialized")
    if not template_service:

    template_service = get_template_service()
    """Get information about a specific template."""
async def get_template_info(template_name: str):
@router.get("/{template_name}")


    return {"templates": templates}
    templates = template_service.get_all_templates_info()

        raise HTTPException(status_code=503, detail="Template service not initialized")
    if not template_service:

    template_service = get_template_service()
    """List all available grading templates."""
async def list_templates():
@router.get("")


router = APIRouter(prefix="/templates", tags=["Templates"])


from web.core.lifespan import get_template_service

from fastapi import APIRouter, HTTPException

