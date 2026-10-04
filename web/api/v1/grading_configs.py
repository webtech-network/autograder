"""Configuration resources: one definition validator and one update path."""

from datetime import timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from web.api.deps import get_db_session, require_integration_token
from web.repositories import GradingConfigRepository
from web.schemas.assignment import (
    GradingConfigCreate,
    GradingConfigUpdate,
    GradingConfigResponse,
)
from autograder.models.contracts.definition import (
    compile_definition,
    DefinitionValidationError,
    GradingDefinition,
)

router = APIRouter(prefix="/configs", tags=["Grading Configurations"])


def _compile(value):
    try:
        return compile_definition(value)
    except DefinitionValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc


def _response(config, response):
    response.headers["ETag"] = f'"{config.version}"'
    # SQLite and pre-migration timestamps are naive UTC; wire timestamps always carry offsets.
    return {
        key: (
            value.replace(tzinfo=timezone.utc)
            if key.endswith("_at") and value.tzinfo is None
            else value
        )
        for key in GradingConfigResponse.model_fields
        if (value := getattr(config, key)) is not None
    } | {
        "definition": config.definition,
        "definition_hash": config.definition_hash,
        "migration_error": config.migration_error,
    }


@router.post("/validate")
async def validate_definition(definition: GradingDefinition):
    compiled = _compile(definition)
    return {
        "definition": compiled.definition.model_dump(mode="json"),
        "definition_hash": compiled.definition_hash,
    }


@router.post("", response_model=GradingConfigResponse)
async def create_grading_config(
    config: GradingConfigCreate, response: Response, session=Depends(get_db_session)
):
    compiled = _compile(config.definition)
    repo = GradingConfigRepository(session)
    if await repo.get_by_external_id(config.external_assignment_id):
        raise HTTPException(
            409, "Configuration already exists; reactivate the existing resource"
        )
    try:
        row = await repo.create(
            external_assignment_id=config.external_assignment_id,
            definition=compiled.definition.model_dump(mode="json"),
            definition_hash=compiled.definition_hash,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Configuration already exists") from exc
    return _response(row, response)


async def _get(repo, config_id=None, external_id=None):
    row = (
        await repo.get_by_id(config_id)
        if config_id is not None
        else await repo.get_by_external_id(external_id)
    )
    if row is None:
        raise HTTPException(404, "Configuration not found")
    return row


@router.get(
    "/id/{config_id}",
    response_model=GradingConfigResponse,
    dependencies=[Depends(require_integration_token)],
)
async def get_grading_config_by_id(
    config_id: int, response: Response, session=Depends(get_db_session)
):
    return _response(
        await _get(GradingConfigRepository(session), config_id=config_id), response
    )


@router.get("", response_model=list[GradingConfigResponse])
async def list_grading_configs(
    response: Response,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_db_session),
):
    rows = await GradingConfigRepository(session).get_active_configs(limit, offset)
    return [_response(row, response) for row in rows]


@router.get("/{external_assignment_id}", response_model=GradingConfigResponse)
async def get_grading_config(
    external_assignment_id: str, response: Response, session=Depends(get_db_session)
):
    return _response(
        await _get(
            GradingConfigRepository(session), external_id=external_assignment_id
        ),
        response,
    )


def _revision(if_match):
    if if_match is None:
        raise HTTPException(
            428, "If-Match with the current quoted revision is required"
        )
    import re

    if not re.fullmatch(r'"[1-9][0-9]*"', if_match):
        raise HTTPException(422, "If-Match must be a quoted positive integer revision")
    return int(if_match[1:-1])


async def _patch(repo, row, payload, if_match, response):
    expected = _revision(if_match)
    changes = payload.model_dump(exclude_unset=True)
    if "definition" in changes:
        compiled = _compile(changes["definition"])
        changes["definition"] = compiled.definition.model_dump(mode="json")
        changes["definition_hash"] = compiled.definition_hash
        changes["migration_error"] = None
    if changes.get("is_active") and changes.get("definition", row.definition) is None:
        raise HTTPException(
            422,
            "A quarantined configuration requires a valid definition before activation",
        )
    changes = {
        key: value for key, value in changes.items() if getattr(row, key) != value
    }
    updated = await repo.conditional_update(row.id, expected, changes)
    if updated is None:
        raise HTTPException(412, "Configuration revision changed; fetch it and retry")
    await repo.session.commit()
    return _response(updated, response)


@router.patch(
    "/external/{external_assignment_id}", response_model=GradingConfigResponse
)
async def update_grading_config_external(
    external_assignment_id: str,
    update: GradingConfigUpdate,
    response: Response,
    if_match: str | None = Header(None),
    session=Depends(get_db_session),
):
    repo = GradingConfigRepository(session)
    return await _patch(
        repo,
        await _get(repo, external_id=external_assignment_id),
        update,
        if_match,
        response,
    )


@router.patch("/{config_id}", response_model=GradingConfigResponse)
async def update_grading_config(
    config_id: int,
    update: GradingConfigUpdate,
    response: Response,
    if_match: str | None = Header(None),
    session=Depends(get_db_session),
):
    repo = GradingConfigRepository(session)
    return await _patch(
        repo, await _get(repo, config_id=config_id), update, if_match, response
    )
