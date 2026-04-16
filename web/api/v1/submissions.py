"""Submission endpoints."""

import asyncio
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.deps import get_db_session, require_integration_token
from web.config.logging import get_logger
from web.core.lifespan import get_grading_tasks
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
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
from web.service.grading_service import grade_submission, GradingRequest


logger = get_logger(__name__)
router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("", response_model=SubmissionResponse)
async def create_submission(
    submission: SubmissionCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Submit code for grading."""
    logger.info(
        "Submission request received: user=%s, assignment=%s, language=%s, files=%s",
        submission.external_user_id,
        submission.external_assignment_id,
        submission.language or "auto",
        [f.filename for f in submission.files],
    )

    # Get grading configuration
    config_repo = GradingConfigRepository(session)
    grading_config = await config_repo.get_by_external_id(submission.external_assignment_id)

    if not grading_config:
        logger.warning(
            "Submission rejected: grading configuration not found for assignment=%s (user=%s)",
            submission.external_assignment_id,
            submission.external_user_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Grading configuration for assignment {submission.external_assignment_id} not found"
        )

    # Determine submission language (override or first supported language)
    submission_language = submission.language
    if submission_language:
        # Validate that the submission language is supported by this assignment
        if submission_language not in grading_config.languages:
            logger.warning(
                "Submission rejected: unsupported language '%s' for assignment=%s (user=%s, supported=%s)",
                submission_language,
                submission.external_assignment_id,
                submission.external_user_id,
                grading_config.languages,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Language '{submission_language}' is not supported for this assignment. "
                       f"Supported languages: {', '.join(grading_config.languages)}"
            )
    else:
        # No language specified, use the first supported language as default
        submission_language = grading_config.languages[0]
        logger.info(
            "No language specified for submission; defaulting to '%s' (assignment=%s, user=%s)",
            submission_language,
            submission.external_assignment_id,
            submission.external_user_id,
        )

    # Convert list of SubmissionFileData to dict format for storage and quick access
    # This indexing by filename allows O(1) file lookups during grading
    submission_files_dict = {
        file_data.filename: {"filename": file_data.filename, "content": file_data.content}
        for file_data in submission.files
    }

    # Create submission record
    submission_repo = SubmissionRepository(session)
    db_submission = await submission_repo.create(
        grading_config_id=grading_config.id,
        external_user_id=submission.external_user_id,
        username=submission.username,
        submission_files=submission_files_dict,
        language=submission_language,
        status=SubmissionStatus.PENDING,
        submission_metadata=submission.metadata,
    )

    # Commit to save submission
    await session.commit()

    # Schedule concurrent grading task using asyncio
    # This allows multiple submissions to be graded simultaneously,
    # fully utilizing the sandbox pool's capacity
    grading_request = GradingRequest(
        submission_id=db_submission.id,
        grading_config_id=grading_config.id,
        template_name=grading_config.template_name,
        criteria_config=grading_config.criteria_config,
        setup_config=grading_config.setup_config,
        feedback_config=grading_config.feedback_config or {},
        include_feedback=grading_config.include_feedback,
        language=db_submission.language,
        username=db_submission.username,
        external_user_id=db_submission.external_user_id,
        submission_files=db_submission.submission_files,
        locale=submission.locale,
    )
    task = asyncio.create_task(grade_submission(grading_request))

    # Track task to prevent garbage collection
    grading_tasks = get_grading_tasks()
    grading_tasks.add(task)
    task.add_done_callback(grading_tasks.discard)

    logger.info(
        "Submission created and grading task scheduled: submission_id=%d, user=%s, assignment=%s, language=%s",
        db_submission.id,
        db_submission.external_user_id,
        submission.external_assignment_id,
        db_submission.language,
    )

    return db_submission


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Get submission by ID with results."""
    logger.info("Fetching submission: submission_id=%d", submission_id)

    repo = SubmissionRepository(session)
    submission = await repo.get_by_id_with_result(submission_id)

    if not submission:
        logger.warning("Submission not found: submission_id=%d", submission_id)
        raise HTTPException(status_code=404, detail="Submission not found")

    # Convert submission_files from storage format to API response format
    # Storage: Dict[str, Dict] -> Response: Dict[str, str]
    formatted_files = {}
    if submission.submission_files:
        for name, data in submission.submission_files.items():
            # Extract content from the stored dict structure
            if isinstance(data, dict):
                # New format: {"filename": "...", "content": "..."}
                formatted_files[name] = data.get("content", "")
            else:
                # Legacy format or unexpected type: convert to string
                formatted_files[name] = str(data)

    # Build response
    response_data = {
        "id": submission.id,
        "grading_config_id": submission.grading_config_id,
        "external_user_id": submission.external_user_id,
        "username": submission.username,
        "status": submission.status,
        "submitted_at": submission.submitted_at,
        "graded_at": submission.graded_at,
        "submission_files": formatted_files,
        "submission_metadata": submission.submission_metadata,
        "final_score": None,
        "feedback": None,
        "result_tree": None,
        "focus": None,
        "pipeline_execution": None,
    }

    # Add result data if available
    if submission.result:
        response_data.update({
            "final_score": submission.result.final_score,
            "feedback": submission.result.feedback,
            "result_tree": submission.result.result_tree,
            "focus": submission.result.focus,
            "pipeline_execution": submission.result.pipeline_execution,
        })

    logger.info(
        "Submission fetched: submission_id=%d, user=%s, status=%s",
        submission.id,
        submission.external_user_id,
        submission.status,
    )
    return response_data


@router.get("/user/{external_user_id}", response_model=List[SubmissionResponse])
async def get_user_submissions(
    external_user_id: str,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """Get all submissions by a user."""
    logger.info(
        "Fetching submissions for user: user=%s, limit=%d, offset=%d",
        external_user_id,
        limit,
        offset,
    )
    repo = SubmissionRepository(session)
    submissions = await repo.get_by_user(external_user_id, limit=limit, offset=offset)
    logger.info("Found %d submission(s) for user=%s", len(submissions), external_user_id)
    return submissions


@router.post("/external-results", response_model=ExternalResultResponse, dependencies=[Depends(require_integration_token)])
async def ingest_external_result(
    payload: ExternalResultCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Ingest an externally computed grading result.

    Creates a submission row and a matching submission_result row from
    results computed outside the cloud instance (e.g. GitHub Action in
    external/private mode).
    """
    logger.info(
        "External result ingestion: user=%s, config_id=%d, status=%s, score=%.2f",
        payload.external_user_id,
        payload.grading_config_id,
        payload.status.value,
        payload.final_score,
    )

    # Validate grading config exists
    config_repo = GradingConfigRepository(session)
    grading_config = await config_repo.get_by_id(payload.grading_config_id)
    if not grading_config:
        logger.warning(
            "External result rejected: grading config not found config_id=%d (user=%s)",
            payload.grading_config_id,
            payload.external_user_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Grading configuration with id {payload.grading_config_id} not found"
        )

    # Validate language is supported by this config
    if payload.language not in grading_config.languages:
        logger.warning(
            "External result rejected: unsupported language '%s' for config_id=%d (supported=%s)",
            payload.language,
            payload.grading_config_id,
            grading_config.languages,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Language '{payload.language}' is not supported for this configuration. "
                   f"Supported languages: {', '.join(grading_config.languages)}"
        )

    # Map external status to internal submission status
    submission_status = (
        SubmissionStatus.COMPLETED
        if payload.status.value == "completed"
        else SubmissionStatus.FAILED
    )

    # Map to pipeline status
    pipeline_status = (
        PipelineStatus.SUCCESS
        if payload.status.value == "completed"
        else PipelineStatus.FAILED
    )

    now = datetime.now(timezone.utc)

    # Create submission record (no files — externally graded)
    submission_repo = SubmissionRepository(session)
    db_submission = await submission_repo.create(
        grading_config_id=grading_config.id,
        external_user_id=payload.external_user_id,
        username=payload.username,
        submission_files={},
        language=payload.language,
        status=submission_status,
        submission_metadata=payload.submission_metadata,
    )
    db_submission.graded_at = now

    # Flush to obtain the submission ID before creating the result row
    await session.flush()

    # Create submission result record
    result_repo = ResultRepository(session)
    await result_repo.create(
        submission_id=db_submission.id,
        final_score=payload.final_score,
        result_tree=payload.result_tree,
        feedback=payload.feedback,
        focus=payload.focus,
        pipeline_execution=payload.pipeline_execution,
        execution_time_ms=payload.execution_time_ms,
        pipeline_status=pipeline_status,
        error_message=payload.error_message,
    )

    await session.commit()

    logger.info(
        "External result ingested: submission_id=%d, config_id=%d, user=%s, score=%.2f, status=%s",
        db_submission.id,
        grading_config.id,
        payload.external_user_id,
        payload.final_score,
        submission_status.value,
    )

    return ExternalResultResponse(
        submission_id=db_submission.id,
        grading_config_id=grading_config.id,
        external_user_id=payload.external_user_id,
        username=payload.username,
        status=submission_status,
        final_score=payload.final_score,
        graded_at=now,
        execution_time_ms=payload.execution_time_ms,
    )
