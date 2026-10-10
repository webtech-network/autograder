"""HTTP transport for durable acceptance, history and authenticated outcomes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from web.api.deps import get_db_session, require_integration_token
from web.database.models.submission import SubmissionStatus
from web.schemas import (
    SubmissionCreate, SubmissionResponse, SubmissionDetailResponse,
    ExternalResultCreate, ExternalResultResponse,
)
from web.service.submission_operations import (
    OperationError, accept_submission, ingest_attested_outcome,
    project_submission, query_history, query_submission,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


async def _operation(awaitable):
    try:
        return await awaitable
    except OperationError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from exc


@router.post("", status_code=202, response_model=SubmissionResponse)
async def create_submission(submission: SubmissionCreate, response: Response, session=Depends(get_db_session)):
    row = await _operation(accept_submission(session, submission))
    response.headers["Location"] = f"/api/v1/submissions/{row.id}"
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


@router.post("/external-results", response_model=ExternalResultResponse,
             dependencies=[Depends(require_integration_token)])
async def ingest_external_result(payload: ExternalResultCreate, session=Depends(get_db_session)):
    return await _operation(ingest_attested_outcome(session, payload))


@router.get("/{submission_id}/details", response_model=SubmissionDetailResponse,
            dependencies=[Depends(require_integration_token)])
async def get_submission_details(submission_id: int, session=Depends(get_db_session)):
    return await _operation(query_submission(session, submission_id, details=True))


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(submission_id: int, session=Depends(get_db_session)):
    return await _operation(query_submission(session, submission_id))
