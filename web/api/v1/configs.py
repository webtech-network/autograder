"""Grading configuration endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.deps import get_db_session
from web.repositories import GradingConfigRepository
from web.schemas import (
    GradingConfigCreate,
    GradingConfigResponse,
    GradingConfigUpdate,
)


router = APIRouter(prefix="/configs", tags=["Grading Configurations"])


@router.post("", response_model=GradingConfigResponse)
async def create_grading_config(
    config: GradingConfigCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new grading configuration."""
    repo = GradingConfigRepository(session)

    # Check if config already exists
    existing = await repo.get_by_external_id(config.external_assignment_id)
    if existing:
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

    return db_config


@router.get("/{external_assignment_id}", response_model=GradingConfigResponse)
async def get_grading_config(
    external_assignment_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Get grading configuration by external assignment ID."""
    repo = GradingConfigRepository(session)
    config = await repo.get_by_external_id(external_assignment_id)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration for assignment {external_assignment_id} not found"
        )

    return config


@router.get("", response_model=List[GradingConfigResponse])
async def list_grading_configs(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """List all grading configurations."""
    repo = GradingConfigRepository(session)
    configs = await repo.get_active_configs(limit=limit, offset=offset)
    return configs


@router.put("/{config_id}", response_model=GradingConfigResponse)
async def update_grading_config(
    config_id: int,
    update: GradingConfigUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update a grading configuration."""
    repo = GradingConfigRepository(session)

    # Get existing config
    config = await repo.get_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    if update_data:
        updated_config = await repo.update(config_id, **update_data)
        return updated_config

    return config

