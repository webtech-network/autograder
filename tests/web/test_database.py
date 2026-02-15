"""Unit tests for database models and repositories."""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from web.database.base import Base
from web.database.models import GradingConfiguration, Submission, SubmissionResult
from web.database.models.submission import SubmissionStatus
from web.database.models.submission_result import PipelineStatus
from web.repositories import (
    GradingConfigRepository,
    SubmissionRepository,
    ResultRepository,
)


# Test database setup
@pytest.fixture
async def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()


# GradingConfiguration tests
@pytest.mark.asyncio
async def test_create_grading_config(db_session):
    """Test creating a grading configuration."""
    repo = GradingConfigRepository(db_session)
    
    config = await repo.create(
        external_assignment_id="test-assignment-1",
        template_name="webdev",
        criteria_config={"tests": ["test1", "test2"]},
        language="python",
    )
    
    assert config.id is not None
    assert config.external_assignment_id == "test-assignment-1"
    assert config.template_name == "webdev"
    assert config.language == "python"
    assert config.is_active is True


@pytest.mark.asyncio
async def test_get_config_by_external_id(db_session):
    """Test retrieving config by external assignment ID."""
    repo = GradingConfigRepository(db_session)
    
    # Create config
    await repo.create(
        external_assignment_id="test-assignment-2",
        template_name="api",
        criteria_config={"tests": ["test1"]},
        language="javascript",
    )
    
    # Retrieve it
    config = await repo.get_by_external_id("test-assignment-2")
    
    assert config is not None
    assert config.external_assignment_id == "test-assignment-2"
    assert config.template_name == "api"


@pytest.mark.asyncio
async def test_get_active_configs(db_session):
    """Test getting all active configurations."""
    repo = GradingConfigRepository(db_session)
    
    # Create multiple configs
    await repo.create(
        external_assignment_id="assignment-1",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    await repo.create(
        external_assignment_id="assignment-2",
        template_name="api",
        criteria_config={},
        language="java",
    )
    
    # Get all active
    configs = await repo.get_active_configs()
    
    assert len(configs) == 2


# Submission tests
@pytest.mark.asyncio
async def test_create_submission(db_session):
    """Test creating a submission."""
    # First create a config
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-3",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    
    # Create submission
    submission_repo = SubmissionRepository(db_session)
    submission = await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-123",
        username="testuser",
        submission_files={"main.py": "print('hello')"},
        language="python",
        status=SubmissionStatus.PENDING,
    )
    
    assert submission.id is not None
    assert submission.external_user_id == "user-123"
    assert submission.username == "testuser"
    assert submission.status == SubmissionStatus.PENDING


@pytest.mark.asyncio
async def test_get_submissions_by_user(db_session):
    """Test getting submissions by user."""
    # Create config
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-4",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    
    # Create multiple submissions for same user
    submission_repo = SubmissionRepository(db_session)
    await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-456",
        username="testuser2",
        submission_files={"main.py": "code1"},
        language="python",
        status=SubmissionStatus.PENDING,
    )
    await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-456",
        username="testuser2",
        submission_files={"main.py": "code2"},
        language="python",
        status=SubmissionStatus.COMPLETED,
    )
    
    # Get user submissions
    submissions = await submission_repo.get_by_user("user-456")
    
    assert len(submissions) == 2


@pytest.mark.asyncio
async def test_update_submission_status(db_session):
    """Test updating submission status."""
    # Create config and submission
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-5",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    
    submission_repo = SubmissionRepository(db_session)
    submission = await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-789",
        username="testuser3",
        submission_files={"main.py": "code"},
        language="python",
        status=SubmissionStatus.PENDING,
    )
    
    # Update status
    updated = await submission_repo.update_status(
        submission.id, SubmissionStatus.PROCESSING
    )
    
    assert updated.status == SubmissionStatus.PROCESSING


# SubmissionResult tests
@pytest.mark.asyncio
async def test_create_submission_result(db_session):
    """Test creating a submission result."""
    # Create config and submission
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-6",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    
    submission_repo = SubmissionRepository(db_session)
    submission = await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-101",
        username="testuser4",
        submission_files={"main.py": "code"},
        language="python",
        status=SubmissionStatus.COMPLETED,
    )
    
    # Create result
    result_repo = ResultRepository(db_session)
    result = await result_repo.create(
        submission_id=submission.id,
        final_score=85.5,
        result_tree={"name": "root", "score": 85.5},
        feedback="Good work!",
        execution_time_ms=1500,
        pipeline_status=PipelineStatus.SUCCESS,
    )
    
    assert result.id is not None
    assert result.submission_id == submission.id
    assert result.final_score == 85.5
    assert result.pipeline_status == PipelineStatus.SUCCESS


@pytest.mark.asyncio
async def test_get_result_by_submission_id(db_session):
    """Test retrieving result by submission ID."""
    # Create config, submission, and result
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-7",
        template_name="webdev",
        criteria_config={},
        language="python",
    )
    
    submission_repo = SubmissionRepository(db_session)
    submission = await submission_repo.create(
        grading_config_id=config.id,
        external_user_id="user-202",
        username="testuser5",
        submission_files={"main.py": "code"},
        language="python",
        status=SubmissionStatus.COMPLETED,
    )
    
    result_repo = ResultRepository(db_session)
    await result_repo.create(
        submission_id=submission.id,
        final_score=90.0,
        execution_time_ms=2000,
        pipeline_status=PipelineStatus.SUCCESS,
    )
    
    # Retrieve result
    result = await result_repo.get_by_submission_id(submission.id)
    
    assert result is not None
    assert result.final_score == 90.0
