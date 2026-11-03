"""HTTP transport for durable acceptance, history and authenticated outcomes."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from web.api.deps import Principal, get_db_session, require_attestation, require_integration_token
from web.database.models.submission import SubmissionStatus
from web.schemas import (
    SubmissionCreate, SubmissionResponse, SubmissionDetailResponse,
    ExternalResultCreate, ExternalResultResponse,
)
from web.service.submission_operations import (
    Idempotency, OperationError, accept_submission, ingest_attested_outcome,
    project_submission, query_history, query_submission,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])
# Restricted producers may only attest finished outcomes (see docs/contracts/AUTH.md).
attestation_router = APIRouter(prefix="/submissions", tags=["Submissions"])


IDEMPOTENCY_KEY = Header(
    None, alias="Idempotency-Key", min_length=1, max_length=255, pattern=r"^[\x21-\x7e]+$",
    description=("Caller-generated key (1-255 visible ASCII characters). Repeating a key with the "
                 "same request returns the original receipt without creating or grading anything; "
                 "the same key with a different request is 409 IDEMPOTENCY_KEY_REUSED."))
REPLAY_RESPONSES = {409: {"description": "Idempotency-Key reused with a different request"}}


def _idempotency(principal, key):
    return Idempotency(principal.name, key) if key is not None else None


def _mark_replay(response, replayed):
    response.headers["Idempotent-Replayed"] = "true" if replayed else "false"


async def _operation(awaitable):
    try:
        return await awaitable
    except OperationError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from exc


@router.post("", status_code=202, response_model=SubmissionResponse, responses=REPLAY_RESPONSES)
async def create_submission(submission: SubmissionCreate, response: Response,
                            idempotency_key: str | None = IDEMPOTENCY_KEY,
                            principal: Principal = Depends(require_integration_token),
                            session=Depends(get_db_session)):
    row, replayed = await _operation(
        accept_submission(session, submission, _idempotency(principal, idempotency_key)))
    response.headers["Location"] = f"/api/v1/submissions/{row.id}"
    _mark_replay(response, replayed)
    return project_submission(row)


@router.get("", response_model=list[SubmissionResponse])
async def history(external_user_id: str | None = None,
                  grading_config_id: int | None = Query(None, gt=0),
                  status: SubmissionStatus | None = None,
                  limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
                  session=Depends(get_db_session)):
    return await query_history(session, external_user_id=external_user_id, grading_config_id=grading_config_id,
                               status=status, limit=limit, offset=offset)


@router.get("/user/{external_user_id}", response_model=list[SubmissionResponse])
async def get_user_submissions(external_user_id: str, limit: int = Query(100, ge=1, le=100),
                               offset: int = Query(0, ge=0), session=Depends(get_db_session)):
    return await query_history(session, external_user_id=external_user_id, limit=limit, offset=offset)


@attestation_router.post("/external-results", response_model=ExternalResultResponse,
                         responses=REPLAY_RESPONSES)
async def ingest_external_result(payload: ExternalResultCreate, response: Response,
                                 idempotency_key: str | None = IDEMPOTENCY_KEY,
                                 principal: Principal = Depends(require_attestation),
                                 session=Depends(get_db_session)):
    receipt, replayed = await _operation(
        ingest_attested_outcome(session, payload, _idempotency(principal, idempotency_key)))
    _mark_replay(response, replayed)
    return receipt


@router.get("/{submission_id}/details", response_model=SubmissionDetailResponse)
async def get_submission_details(submission_id: int, session=Depends(get_db_session)):
    return await _operation(query_submission(session, submission_id, details=True))


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(submission_id: int, session=Depends(get_db_session)):
    return await _operation(query_submission(session, submission_id))
