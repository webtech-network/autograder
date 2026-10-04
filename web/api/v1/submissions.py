"""Bind validated definitions once; expose compact reads and exact shared outcomes."""

import asyncio
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from web.api.deps import get_db_session, require_integration_token
from web.core.lifespan import get_grading_tasks
from web.database.models.submission import SubmissionStatus
from web.repositories import (
    GradingConfigRepository,
    SubmissionRepository,
    ResultRepository,
)
from web.schemas import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionDetailResponse,
    ExternalResultCreate,
    ExternalResultResponse,
)
from web.service.grading_service import (
    GradingRequest,
    grade_submission,
    persist_outcome,
)
from autograder.models.contracts.definition import (
    compile_definition,
    select_language,
    DefinitionValidationError,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def _utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value is not None and value.tzinfo is None
        else value
    )


def project_submission(row, *, details=False):
    result = row.result
    outcome = result.outcome if result else None
    error = outcome.get("error") if outcome else None
    if result and not outcome and row.status == SubmissionStatus.FAILED:
        error = {
            "code": "LEGACY_UNVERIFIED",
            "message": "This historical execution predates the verified outcome contract.",
            "category": "internal",
            "retryable": False,
            "correlation_id": f"legacy-submission-{row.id}",
        }
    # Legacy failures carried a numeric zero. It is never an authoritative grade.
    score = (
        outcome["score"]
        if outcome
        else (
            result.final_score
            if result and row.status == SubmissionStatus.COMPLETED
            else None
        )
    )
    data = {
        "id": row.id,
        "grading_config_id": row.grading_config_id,
        "external_user_id": row.external_user_id,
        "username": row.username,
        "language": row.language,
        "status": row.status,
        "submitted_at": _utc(row.submitted_at),
        "graded_at": _utc(row.graded_at),
        "final_score": score,
        "execution_time_ms": (
            outcome["duration_ms"]
            if outcome
            else (result.execution_time_ms if result else None)
        ),
        "provenance": (
            outcome["provenance"]
            if outcome
            else (
                {
                    "schema_version": "1.0",
                    "definition_hash": row.definition_hash,
                    "reference": str(row.grading_config_id),
                    "revision": row.configuration_version,
                }
                if row.definition_hash
                else None
            )
        ),
        "provenance_status": (
            "bound_snapshot" if row.definition_hash else "unverified_legacy"
        ),
        "error": error,
        "feedback_status": outcome["feedback"]["status"] if outcome else None,
        "comparison_status": outcome["comparison"]["status"] if outcome else None,
    }
    if details:
        data.update(
            submission_files={
                name: (
                    value.get("content", "") if isinstance(value, dict) else str(value)
                )
                for name, value in row.submission_files.items()
            },
            submission_metadata=row.submission_metadata,
            definition_snapshot=row.definition_snapshot,
            outcome=outcome,
            diagnostics=result.diagnostics if result else None,
        )
    return data


def _compile(value):
    try:
        return compile_definition(value)
    except DefinitionValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc


@router.post("", response_model=SubmissionResponse)
async def create_submission(
    submission: SubmissionCreate, session=Depends(get_db_session)
):
    config = await GradingConfigRepository(session).get_by_external_id(
        submission.external_assignment_id
    )
    if config is None:
        raise HTTPException(404, "Grading configuration not found")
    if not config.is_active or config.definition is None:
        raise HTTPException(
            409, "Grading configuration is inactive or requires migration"
        )
    compiled = _compile(config.definition)
    try:
        language = select_language(compiled.definition, submission.language)
    except DefinitionValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(
            422,
            detail=[
                {"code": "INVALID_LANGUAGE", "path": ["language"], "message": str(exc)}
            ],
        ) from exc
    filenames = [file.filename for file in submission.files]
    if len(set(filenames)) != len(filenames):
        raise HTTPException(422, "Submission filenames must be unique")
    files = {file.filename: file.model_dump() for file in submission.files}
    repo = SubmissionRepository(session)
    row = await repo.create(
        grading_config_id=config.id,
        external_user_id=submission.external_user_id,
        username=submission.username,
        submission_files=files,
        language=language.value,
        submission_metadata=submission.metadata,
        definition_snapshot=compiled.definition.model_dump(mode="json"),
        definition_hash=compiled.definition_hash,
        configuration_version=config.version,
    )
    await session.commit()
    request = GradingRequest(
        submission_id=row.id,
        grading_config_id=config.id,
        definition=row.definition_snapshot,
        configuration_version=row.configuration_version,
        definition_hash=row.definition_hash,
        language=row.language,
        username=row.username,
        external_user_id=row.external_user_id,
        submission_files=row.submission_files,
        locale=submission.locale or "en",
        evaluation_scope=(
            submission.evaluation_scope.model_dump()
            if submission.evaluation_scope
            else None
        ),
    )
    task = asyncio.create_task(grade_submission(request))
    tasks = get_grading_tasks()
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    # Newly created row has no loaded result relationship; load explicitly rather than trigger async lazy I/O.
    row = await repo.get_by_id_with_result(row.id)
    return project_submission(row)


@router.get("", response_model=list[SubmissionResponse])
async def history(
    external_user_id: str | None = None,
    grading_config_id: int | None = Query(None, gt=0),
    status: SubmissionStatus | None = None,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_db_session),
):
    rows = await SubmissionRepository(session).history(
        external_user_id=external_user_id,
        grading_config_id=grading_config_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [project_submission(row) for row in rows]


@router.get("/user/{external_user_id}", response_model=list[SubmissionResponse])
async def get_user_submissions(
    external_user_id: str,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_db_session),
):
    return await history(
        external_user_id=external_user_id,
        grading_config_id=None,
        status=None,
        limit=limit,
        offset=offset,
        session=session,
    )


def _check_attested_tree(outcome, compiled):
    """Attestation may not change criterion placement or scoring ratios."""
    from math import isclose

    if outcome["status"] != "completed":
        return

    def mismatch():
        raise HTTPException(
            422,
            "Result tree structure, identities or scoring weights do not match its definition snapshot",
        )

    def holder(expected, actual):
        if actual["name"] != expected.name:
            mismatch()
        for key in ("subjects", "tests"):
            children = getattr(expected, key)
            actual_children = actual.get(key) or []
            if len(children) != len(actual_children):
                mismatch()
            factor = 100.0
            if expected.subjects and expected.tests:
                factor = (
                    expected.subjects_weight
                    if key == "subjects"
                    else 100.0 - expected.subjects_weight
                )
            max_weight = max((child.weight for child in children), default=0)
            scaled_total = (
                sum(child.weight / max_weight for child in children)
                if max_weight
                else 0
            )
            for child, result in zip(children, actual_children):
                normalized_weight = (
                    child.weight / max_weight / scaled_total * factor
                    if max_weight
                    else factor / len(children)
                )
                if not isclose(result["weight"], normalized_weight, abs_tol=0.00001):
                    mismatch()
                if key == "tests":
                    if (
                        result["id"] != child.criterion_id
                        or result["evaluator"] != child.test_function.name
                        or result["name"] != child.name
                        or result.get("file_target") != child.file_target
                    ):
                        mismatch()
                else:
                    holder(child, result)

    tree = outcome["tree"]
    for category in ("base", "bonus", "penalty"):
        expected = getattr(compiled.criteria_tree, category)
        actual = tree.get(category)
        if (expected is None) != (actual is None):
            mismatch()
        if expected:
            if not isclose(expected.weight, actual["weight"], abs_tol=0.00001):
                mismatch()
            holder(expected, actual)


@router.post(
    "/external-results",
    response_model=ExternalResultResponse,
    dependencies=[Depends(require_integration_token)],
)
async def ingest_external_result(
    payload: ExternalResultCreate, session=Depends(get_db_session)
):
    config = await GradingConfigRepository(session).get_by_id(payload.grading_config_id)
    if config is None:
        raise HTTPException(404, "Grading configuration not found")
    compiled = _compile(payload.definition_snapshot)
    outcome = payload.outcome.model_dump(mode="json")
    provenance = outcome["provenance"]
    if provenance["definition_hash"] != compiled.definition_hash or provenance.get(
        "reference"
    ) != str(config.id):
        raise HTTPException(
            422, "Outcome provenance does not match its definition snapshot/resource"
        )
    revision = provenance.get("revision")
    if revision is None or revision > config.version:
        raise HTTPException(
            422, "Outcome must attest a known positive configuration revision"
        )
    if (
        revision == config.version
        and compiled.definition_hash != config.definition_hash
    ):
        raise HTTPException(
            422, "Current revision attestation must match the stored definition hash"
        )
    if (
        outcome["language"] != payload.language
        or payload.language not in compiled.definition.languages
    ):
        raise HTTPException(
            422, "Outcome language does not match its definition snapshot"
        )
    _check_attested_tree(outcome, compiled)
    repo = SubmissionRepository(session)
    row = await repo.create(
        grading_config_id=config.id,
        external_user_id=payload.external_user_id,
        username=payload.username,
        submission_files={},
        language=payload.language,
        submission_metadata=payload.submission_metadata,
        definition_snapshot=compiled.definition.model_dump(mode="json"),
        definition_hash=compiled.definition_hash,
        configuration_version=revision,
    )
    await persist_outcome(ResultRepository(session), repo, row.id, outcome)
    await session.commit()
    return {
        "submission_id": row.id,
        "grading_config_id": config.id,
        "status": row.status,
        "final_score": outcome["score"],
        "language": row.language,
        "provenance": provenance,
        "graded_at": _utc(row.graded_at),
        "execution_time_ms": outcome["duration_ms"],
    }


@router.get(
    "/{submission_id}/details",
    response_model=SubmissionDetailResponse,
    dependencies=[Depends(require_integration_token)],
)
async def get_submission_details(submission_id: int, session=Depends(get_db_session)):
    row = await SubmissionRepository(session).get_by_id_with_result(submission_id)
    if row is None:
        raise HTTPException(404, "Submission not found")
    return project_submission(row, details=True)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(submission_id: int, session=Depends(get_db_session)):
    row = await SubmissionRepository(session).get_by_id_with_result(
        submission_id, include_files=False
    )
    if row is None:
        raise HTTPException(404, "Submission not found")
    return project_submission(row)
