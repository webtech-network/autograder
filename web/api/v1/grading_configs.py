"""Grading configuration endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.deps import get_db_session
from web.config.logging import get_logger
from web.repositories import GradingConfigRepository
from web.schemas import (
    GradingConfigCreate,
    GradingConfigResponse,
    GradingConfigUpdate,
)


logger = get_logger(__name__)
router = APIRouter(prefix="/configs", tags=["Grading Configurations"])


@router.post("", response_model=GradingConfigResponse)
async def create_grading_config(
    config: GradingConfigCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new grading configuration."""
    logger.info(
        "Creating grading configuration: assignment=%s, template=%s, languages=%s",
        config.external_assignment_id,
        config.template_name,
        config.languages,
    )
    repo = GradingConfigRepository(session)

    # Check if config already exists
    existing = await repo.get_by_external_id(config.external_assignment_id)
    if existing:
        logger.warning(
            "Grading configuration already exists: assignment=%s (config_id=%d)",
            config.external_assignment_id,
            existing.id,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Configuration for assignment {config.external_assignment_id} already exists"
        )

    # Create new configuration
    db_config = await repo.create(
        external_assignment_id=config.external_assignment_id,
        template_name=config.template_name,
        criteria_config=config.criteria_config,
        languages=config.languages,
        setup_config=config.setup_config,
    )

    logger.info(
        "Grading configuration created: config_id=%d, assignment=%s, template=%s",
        db_config.id,
        db_config.external_assignment_id,
        db_config.template_name,
    )
    return db_config


@router.get("/{external_assignment_id}", response_model=GradingConfigResponse)
async def get_grading_config(
    external_assignment_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Get grading configuration by external assignment ID."""
    logger.info("Fetching grading configuration: assignment=%s", external_assignment_id)
    repo = GradingConfigRepository(session)
    config = await repo.get_by_external_id(external_assignment_id)

    if not config:
        logger.warning("Grading configuration not found: assignment=%s", external_assignment_id)
        raise HTTPException(
            status_code=404,
            detail=f"Configuration for assignment {external_assignment_id} not found"
        )

    logger.info(
        "Grading configuration fetched: config_id=%d, assignment=%s, template=%s",
        config.id,
        config.external_assignment_id,
        config.template_name,
    )
    return config


@router.get("", response_model=List[GradingConfigResponse])
async def list_grading_configs(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """List all grading configurations."""
    logger.info("Listing grading configurations: limit=%d, offset=%d", limit, offset)
    repo = GradingConfigRepository(session)
    configs = await repo.get_active_configs(limit=limit, offset=offset)
    logger.info("Found %d grading configuration(s)", len(configs))
    return configs


@router.put("/{config_id}", response_model=GradingConfigResponse)
async def update_grading_config(
    config_id: int,
    update: GradingConfigUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update a grading configuration."""
    logger.info("Updating grading configuration: config_id=%d", config_id)
    repo = GradingConfigRepository(session)

    # Get existing config
    config = await repo.get_by_id(config_id)
    if not config:
        logger.warning("Grading configuration not found for update: config_id=%d", config_id)
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    if update_data:
        updated_config = await repo.update(config_id, **update_data)
        logger.info(
            "Grading configuration updated: config_id=%d, fields=%s",
            config_id,
            list(update_data.keys()),
        )
        return updated_config

    logger.info("No fields to update for grading configuration: config_id=%d", config_id)
    return config


@router.put("/external/{external_assignment_id}", response_model=GradingConfigResponse)
async def update_grading_config_external(
    external_assignment_id: str,
    update: GradingConfigUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update a grading configuration by its external assignment ID."""
    logger.info("Updating grading configuration by external ID: assignment=%s", external_assignment_id)
    repo = GradingConfigRepository(session)

    # Get existing config
    config = await repo.get_by_external_id(external_assignment_id)
    if not config:
        logger.warning("Grading configuration not found for update: assignment=%s", external_assignment_id)
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    if update_data:
        updated_config = await repo.update_by_external_id(external_assignment_id, **update_data)
        logger.info(
            "Grading configuration updated by external ID: assignment=%s, fields=%s",
            external_assignment_id,
            list(update_data.keys()),
        )
        return updated_config

    logger.info("No fields to update for grading configuration: assignment=%s", external_assignment_id)
    return config
