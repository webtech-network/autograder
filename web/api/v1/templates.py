"""Template library endpoints."""

from fastapi import APIRouter, HTTPException

from web.config.logging import get_logger
from web.core.lifespan import get_template_service


logger = get_logger(__name__)
router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("")
async def list_templates():
    """List all available grading templates."""
    logger.info("Listing all available grading templates")
    template_service = get_template_service()

    if not template_service:
        logger.error("Template service not initialized when listing templates")
        raise HTTPException(status_code=503, detail="Template service not initialized")

    templates = template_service.get_all_templates_info()
    logger.info("Returned %d template(s)", len(templates))
    return {"templates": templates}


@router.get("/{template_name}")
async def get_template_info(template_name: str):
    """Get information about a specific template."""
    logger.info("Fetching template info: template=%s", template_name)
    template_service = get_template_service()

    if not template_service:
        logger.error("Template service not initialized when fetching template: template=%s", template_name)
        raise HTTPException(status_code=503, detail="Template service not initialized")

    try:
        template_info = template_service.get_template_info(template_name)
        logger.info("Template info returned: template=%s", template_name)
        return template_info
    except KeyError as e:
        logger.warning("Template not found: template=%s", template_name)
        raise HTTPException(status_code=404, detail=str(e)) from e


