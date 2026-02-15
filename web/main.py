"""FastAPI Web API for the Autograder system."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission as AutograderSubmission
from autograder.services.template_library_service import TemplateLibraryService
from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language

from web.config.logging import setup_logging, get_logger
from web.database import init_db, get_session
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
from web.repositories import (
    GradingConfigRepository,
    SubmissionRepository,
    ResultRepository,
)
from web.schemas import (
    GradingConfigCreate,
    GradingConfigResponse,
    GradingConfigUpdate,
    SubmissionCreate,
    SubmissionResponse,
    SubmissionDetailResponse,
)


# Setup logging
JSON_LOGS = os.getenv("JSON_LOGS", "false").lower() == "true"
setup_logging(json_logs=JSON_LOGS)
logger = get_logger(__name__)

# Global state
template_service: Optional[TemplateLibraryService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: startup and shutdown.
    
    Startup:
    - Initialize database
    - Initialize sandbox manager
    - Load template library
    
    Shutdown:
    - Clean up resources
    """
    global template_service
    
    # Startup
    logger.info("Starting Autograder Web API...")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")
    
    # Initialize sandbox manager
    logger.info("Initializing sandbox manager...")

    # Load pool configurations from YAML file
    config_file = os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml")
    try:
        pool_configs = SandboxPoolConfig.load_from_yaml(config_file)
        logger.info(f"Loaded sandbox configurations from {config_file}")
    except FileNotFoundError as e:
        logger.error(f"Sandbox configuration file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading sandbox configuration: {e}")
        raise

    initialize_sandbox_manager(pool_configs)
    logger.info(f"Sandbox manager initialized with {len(pool_configs)} language pools")

    # Initialize template library
    logger.info("Loading template library...")
    template_service = TemplateLibraryService.get_instance()
    logger.info("Template library loaded successfully")
    
    logger.info("Autograder Web API ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Autograder Web API...")

    # Explicitly shutdown sandbox manager to clean up all containers
    try:
        manager = get_sandbox_manager()
        logger.info("Shutting down sandbox manager...")
        manager.shutdown()
        logger.info("Sandbox manager shutdown complete")
    except Exception as e:
        logger.error(f"Error during sandbox manager shutdown: {e}")

    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Autograder Web API",
    description="RESTful API for code submission grading",
    version="1.0.0",
    lifespan=lifespan,
)


# Dependency to get database session
async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    async with get_session() as session:
        yield session


# Health and readiness endpoints
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/v1/ready")
async def readiness_check():
    """Readiness check for orchestration platforms."""
    global template_service
    
    ready = template_service is not None
    status_code = 200 if ready else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# Template endpoints
@app.get("/api/v1/templates")
async def list_templates():
    """List all available grading templates."""
    global template_service
    
    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not initialized")
    
    templates = template_service.get_all_templates_info()
    return {"templates": templates}


@app.get("/api/v1/templates/{template_name}")
async def get_template_info(template_name: str):
    """Get information about a specific template."""
    global template_service
    
    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not initialized")
    
    try:
        template_info = template_service.get_template_info(template_name)
        return template_info
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Grading configuration endpoints
@app.post("/api/v1/configs", response_model=GradingConfigResponse)
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
        language=config.language,
    )
    
    return db_config


@app.get("/api/v1/configs/{external_assignment_id}", response_model=GradingConfigResponse)
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


@app.get("/api/v1/configs", response_model=List[GradingConfigResponse])
async def list_grading_configs(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """List all grading configurations."""
    repo = GradingConfigRepository(session)
    configs = await repo.get_active_configs(limit=limit, offset=offset)
    return configs


@app.put("/api/v1/configs/{config_id}", response_model=GradingConfigResponse)
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


# Submission endpoints
@app.post("/api/v1/submissions", response_model=SubmissionResponse)
async def create_submission(
    submission: SubmissionCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Submit code for grading."""
    # Get grading configuration
    config_repo = GradingConfigRepository(session)
    grading_config = await config_repo.get_by_external_id(submission.external_assignment_id)
    
    if not grading_config:
        raise HTTPException(
            status_code=404,
            detail=f"Grading configuration for assignment {submission.external_assignment_id} not found"
        )
    
    # Create submission record
    submission_repo = SubmissionRepository(session)
    db_submission = await submission_repo.create(
        grading_config_id=grading_config.id,
        external_user_id=submission.external_user_id,
        username=submission.username,
        submission_files=submission.files,
        language=submission.language or grading_config.language,
        status=SubmissionStatus.PENDING,
        submission_metadata=submission.metadata,
    )
    
    # Commit to save submission
    await session.commit()
    
    # Schedule background grading task
    background_tasks.add_task(
        grade_submission,
        submission_id=db_submission.id,
        grading_config_id=grading_config.id,
        template_name=grading_config.template_name,
        criteria_config=grading_config.criteria_config,
        language=db_submission.language,
        username=db_submission.username,
        external_user_id=db_submission.external_user_id,
        submission_files=db_submission.submission_files,
    )
    
    return db_submission


@app.get("/api/v1/submissions/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Get submission by ID with results."""
    repo = SubmissionRepository(session)
    submission = await repo.get_by_id_with_result(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Build response
    response_data = {
        "id": submission.id,
        "grading_config_id": submission.grading_config_id,
        "external_user_id": submission.external_user_id,
        "username": submission.username,
        "status": submission.status,
        "submitted_at": submission.submitted_at,
        "graded_at": submission.graded_at,
        "submission_files": submission.submission_files,
        "submission_metadata": submission.submission_metadata,
        "final_score": None,
        "feedback": None,
        "result_tree": None,
    }
    
    # Add result data if available
    if submission.result:
        response_data.update({
            "final_score": submission.result.final_score,
            "feedback": submission.result.feedback,
            "result_tree": submission.result.result_tree,
        })
    
    return response_data


@app.get("/api/v1/submissions/user/{external_user_id}", response_model=List[SubmissionResponse])
async def get_user_submissions(
    external_user_id: str,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """Get all submissions by a user."""
    repo = SubmissionRepository(session)
    submissions = await repo.get_by_user(external_user_id, limit=limit, offset=offset)
    return submissions


async def grade_submission(
    submission_id: int,
    grading_config_id: int,
    template_name: str,
    criteria_config: dict,
    language: str,
    username: str,
    external_user_id: str,
    submission_files: dict,
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
                include_feedback=True,
                grading_criteria=criteria_config,
                feedback_config=None,
                setup_config={},  # Empty dict triggers sandbox creation if needed
                custom_template=None,
                feedback_mode="default",
                export_results=False
            )
            
            # Convert to Autograder Submission object
            autograder_submission = AutograderSubmission(
                username=username,
                user_id=external_user_id,
                assignment_id=grading_config_id,
                submission_files=submission_files,
                language=Language[language.upper()] if language else None
            )
            
            # Run pipeline (sandbox management is handled internally by pipeline)
            pipeline_execution = pipeline.run(autograder_submission)
            
            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract results
            if pipeline_execution.result:
                final_score = pipeline_execution.result.final_score
                feedback = pipeline_execution.result.feedback
                result_tree = pipeline_execution.result.result_tree
                
                # Convert result_tree to dict for JSON storage
                result_tree_dict = None
                if result_tree:
                    result_tree_dict = {
                        "name": result_tree.name,
                        "score": result_tree.score,
                        "max_score": result_tree.max_score,
                        "children": [_node_to_dict(child) for child in result_tree.children] if result_tree.children else []
                    }
                
                # Store result
                await result_repo.create(
                    submission_id=submission_id,
                    final_score=final_score,
                    result_tree=result_tree_dict,
                    feedback=feedback,
                    execution_time_ms=execution_time_ms,
                    pipeline_status=PipelineStatus.SUCCESS,
                )
                
                # Update submission status
                await submission_repo.update(
                    submission_id,
                    status=SubmissionStatus.COMPLETED,
                    graded_at=datetime.now(timezone.utc)
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
                
                await result_repo.create(
                    submission_id=submission_id,
                    final_score=0.0,
                    execution_time_ms=execution_time_ms,
                    pipeline_status=PipelineStatus.FAILED,
                    error_message=error_msg,
                    failed_at_step=str(last_step.step) if pipeline_execution.step_results else None
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
    """Convert a ResultTree node to dictionary."""
    return {
        "name": node.name,
        "score": node.score,
        "max_score": node.max_score,
        "children": [_node_to_dict(child) for child in node.children] if node.children else []
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
