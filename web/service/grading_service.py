"""Grading service for background submission processing."""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission as AutograderSubmission, SubmissionFile
from autograder.utils.feedback_generator import generate_preflight_feedback
from sandbox_manager.models.sandbox_models import Language
from web.config.logging import get_logger
from web.database import get_session
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
from web.repositories import SubmissionRepository, ResultRepository
from autograder.serializers.pipeline_execution_serializer import PipelineExecutionSerializer


logger = get_logger(__name__)


@dataclass
class GradingRequest:
    """Encapsulates all parameters needed to grade a submission."""
    submission_id: int
    grading_config_id: int
    template_name: str
    criteria_config: dict
    setup_config: dict
    language: str
    username: str
    external_user_id: str
    submission_files: dict
    locale: str = "en"


async def grade_submission(request: GradingRequest) -> None:
    """
    Background task to grade a submission.

    This function runs the autograder pipeline on the submission and stores results.
    """
    logger.info(
        "Starting grading for submission %d (user: %s)",
        request.submission_id, request.username
    )
    start_time = time.time()

    async with get_session() as session:
        submission_repo = SubmissionRepository(session)
        result_repo = ResultRepository(session)

        try:
            await submission_repo.update_status(request.submission_id, SubmissionStatus.PROCESSING)
            await session.commit()
            logger.info("Submission %d status updated to PROCESSING", request.submission_id)

            pipeline_execution = await _run_pipeline(request)
            execution_time_ms = int((time.time() - start_time) * 1000)

            if pipeline_execution.result:
                await _persist_success(result_repo, submission_repo, request, pipeline_execution, execution_time_ms)
            else:
                await _persist_failure(result_repo, submission_repo, request, pipeline_execution, execution_time_ms)

            await session.commit()

        except Exception as exc:  # pylint: disable=broad-exception-caught
            execution_time_ms = int((time.time() - start_time) * 1000)
            await result_repo.create(
                submission_id=request.submission_id,
                final_score=0.0,
                execution_time_ms=execution_time_ms,
                pipeline_status=PipelineStatus.INTERRUPTED,
                error_message=str(exc),
            )
            await submission_repo.update_status(request.submission_id, SubmissionStatus.FAILED)
            await session.commit()
            logger.error(
                "Error grading submission %d: %s",
                request.submission_id, str(exc),
                exc_info=True
            )


async def _run_pipeline(request: GradingRequest):
    """Build the autograder pipeline and run it in a thread."""
    pipeline = build_pipeline(
        template_name=request.template_name,
        include_feedback=True,
        grading_criteria=request.criteria_config,
        feedback_config={},
        setup_config=request.setup_config if request.setup_config else {},
        custom_template=None,
    )

    files_to_grade = {
        name: SubmissionFile(filename=f["filename"], content=f["content"])
        for name, f in request.submission_files.items()
    }

    autograder_submission = AutograderSubmission(
        username=request.username,
        user_id=request.external_user_id,
        assignment_id=request.grading_config_id,
        submission_files=files_to_grade,
        language=Language[request.language.upper()] if request.language else None,
        locale=request.locale,
    )

    return await asyncio.to_thread(pipeline.run, autograder_submission)


async def _persist_success(result_repo, submission_repo, request: GradingRequest, pipeline_execution, execution_time_ms: int) -> None:
    """Store successful grading results and update submission status."""
    result = pipeline_execution.result
    result_tree_dict = None
    if result.result_tree:
        result_tree_dict = {
            "final_score": result.final_score,
            "children": _node_to_dict(result.result_tree.root),
        }

    focus_dict = result.focus.to_dict() if result.focus else None
    pipeline_summary = PipelineExecutionSerializer.serialize(pipeline_execution)

    await result_repo.create(
        submission_id=request.submission_id,
        final_score=result.final_score,
        result_tree=result_tree_dict,
        feedback=result.feedback,
        focus=focus_dict,
        pipeline_execution=pipeline_summary,
        execution_time_ms=execution_time_ms,
        pipeline_status=PipelineStatus.SUCCESS,
    )

    await submission_repo.update(
        request.submission_id,
        status=SubmissionStatus.COMPLETED,
        graded_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    logger.info(
        "Submission %d graded successfully. Score: %s, Time: %dms",
        request.submission_id, result.final_score, execution_time_ms
    )


async def _persist_failure(result_repo, submission_repo, request: GradingRequest, pipeline_execution, execution_time_ms: int) -> None:
    """Store failed grading results and update submission status."""
    error_msg = "Pipeline failed to produce results"
    if pipeline_execution.step_results:
        last_step = pipeline_execution.get_previous_step()
        if last_step and last_step.error:
            error_msg = last_step.error

    logger.warning("Submission %d pipeline failed: %s", request.submission_id, error_msg)

    pipeline_summary = PipelineExecutionSerializer.serialize(pipeline_execution)

    feedback = None
    failed_step_name = pipeline_summary.get("failed_at_step")
    if failed_step_name == "PreFlightStep":
        feedback = generate_preflight_feedback(pipeline_summary, locale=request.locale)

    await result_repo.create(
        submission_id=request.submission_id,
        final_score=0.0,
        feedback=feedback,
        pipeline_execution=pipeline_summary,
        execution_time_ms=execution_time_ms,
        pipeline_status=PipelineStatus.FAILED,
        error_message=error_msg,
        failed_at_step=failed_step_name,
    )

    await submission_repo.update_status(request.submission_id, SubmissionStatus.FAILED)


def _node_to_dict(node) -> dict:
    """
    Recursively convert ResultTree nodes to a serializable dictionary.
    Leverages the native to_dict() methods in the ResultTree models.
    """
    if node is None:
        return {}

    if hasattr(node, "to_dict") and callable(getattr(node, "to_dict")):
        return node.to_dict()

    if isinstance(node, list):
        return [_node_to_dict(child) for child in node]

    return {}
