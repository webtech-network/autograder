"""Grading service for background submission processing."""

import asyncio
import time
from datetime import datetime, timezone

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission as AutograderSubmission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language
from web.config.logging import get_logger
from web.database import get_session
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
from web.repositories import SubmissionRepository, ResultRepository
from autograder.serializers.pipeline_execution_serializer import PipelineExecutionSerializer


logger = get_logger(__name__)


async def grade_submission(
    submission_id: int,
    grading_config_id: int,
    template_name: str,
    criteria_config: dict,
    setup_config: dict,
    language: str,
    username: str,
    external_user_id: str,
    submission_files: dict,
    locale: str = "en",
):
    """
    Background task to grade a submission.

    This function runs the autograder pipeline on the submission and stores results.
    """
    logger.info(f"Starting grading for submission {submission_id} (user: {username})")
    start_time = time.time()

    async with get_session() as session:
        submission_repo = SubmissionRepository(session)
        result_repo = ResultRepository(session)

        try:
            # Update status to processing
            await submission_repo.update_status(submission_id, SubmissionStatus.PROCESSING)
            await session.commit()
            logger.info(f"Submission {submission_id} status updated to PROCESSING")

            # Build autograder pipeline
            pipeline = build_pipeline(
                template_name=template_name,
                include_feedback=False,  # Keep False for now
                grading_criteria=criteria_config,
                feedback_config=None,
                setup_config=setup_config if setup_config else {},
                custom_template=None,  # Keep None to use default template behavior
            )

            files_to_grade = {
                name: SubmissionFile(filename=f["filename"], content=f["content"])
                for name, f in submission_files.items()
            }

            # Convert to Autograder Submission object
            autograder_submission = AutograderSubmission(
                username=username,
                user_id=external_user_id,
                assignment_id=grading_config_id,
                submission_files=files_to_grade,
                language=Language[language.upper()] if language else None,
                locale=locale,
            )

            # Run pipeline in a thread to avoid blocking the event loop
            # This allows multiple submissions to be graded concurrently,
            # each acquiring their own sandbox container from the pool
            pipeline_execution = await asyncio.to_thread(pipeline.run, autograder_submission)

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Extract results
            if pipeline_execution.result:
                final_score = pipeline_execution.result.final_score
                feedback = pipeline_execution.result.feedback
                result_tree = pipeline_execution.result.result_tree
                focus = pipeline_execution.result.focus

                # Convert result_tree to dict for JSON storage
                result_tree_dict = None
                if result_tree:
                    result_tree_dict = {
                        "final_score": pipeline_execution.result.final_score,
                        "children": _node_to_dict(result_tree.root)
                    }

                # Convert focus to dict for JSON storage
                focus_dict = None
                if focus:
                    focus_dict = focus.to_dict()

                pipeline_summary = PipelineExecutionSerializer.serialize(pipeline_execution)

                # Store result
                await result_repo.create(
                    submission_id=submission_id,
                    final_score=final_score,
                    result_tree=result_tree_dict,
                    feedback=feedback,
                    focus=focus_dict,
                    pipeline_execution=pipeline_summary,
                    execution_time_ms=execution_time_ms,
                    pipeline_status=PipelineStatus.SUCCESS,
                )

                # Update submission status
                await submission_repo.update(
                    submission_id,
                    status=SubmissionStatus.COMPLETED,
                    graded_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )

                logger.info(
                    f"Submission {submission_id} graded successfully. "
                    f"Score: {final_score}, Time: {execution_time_ms}ms"
                )
            else:
                # Pipeline failed
                error_msg = "Pipeline failed to produce results"
                if pipeline_execution.step_results:
                    last_step = pipeline_execution.get_previous_step()
                    if last_step and last_step.error:
                        error_msg = last_step.error

                logger.warning(f"Submission {submission_id} pipeline failed: {error_msg}")

                # Generate pipeline execution summary
                pipeline_summary = PipelineExecutionSerializer.serialize(pipeline_execution)

                # Generate enhanced feedback for preflight failures
                from autograder.utils.feedback_generator import generate_preflight_feedback
                feedback = None
                failed_step_name = pipeline_summary.get("failed_at_step")
                if failed_step_name == "PreFlightStep":
                    feedback = generate_preflight_feedback(pipeline_summary, locale=locale)

                await result_repo.create(
                    submission_id=submission_id,
                    final_score=0.0,
                    feedback=feedback,
                    pipeline_execution=pipeline_summary,
                    execution_time_ms=execution_time_ms,
                    pipeline_status=PipelineStatus.FAILED,
                    error_message=error_msg,
                    failed_at_step=failed_step_name
                )

                await submission_repo.update_status(submission_id, SubmissionStatus.FAILED)

            await session.commit()

        except Exception as e:
            # Handle unexpected errors
            execution_time_ms = int((time.time() - start_time) * 1000)

            await result_repo.create(
                submission_id=submission_id,
                final_score=0.0,
                execution_time_ms=execution_time_ms,
                pipeline_status=PipelineStatus.INTERRUPTED,
                error_message=str(e),
            )

            await submission_repo.update_status(submission_id, SubmissionStatus.FAILED)
            await session.commit()

            logger.error(
                f"Error grading submission {submission_id}: {str(e)}",
                exc_info=True
            )


def _node_to_dict(node) -> dict:
    """
    Recursively convert ResultTree nodes to a serializable dictionary.
    Leverages the native to_dict() methods in the ResultTree models.
    """
    if node is None:
        return {}

    # If the node has its own to_dict method (like ResultTree, RootResultNode, etc.)
    if hasattr(node, 'to_dict') and callable(getattr(node, 'to_dict')):
        return node.to_dict()

    # Fallback for unexpected types or raw lists of children
    if isinstance(node, list):
        return [_node_to_dict(child) for child in node]

    return {}

