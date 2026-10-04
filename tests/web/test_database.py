from tests.web.test_contracts_v1 import definition

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


@pytest.fixture
async def db_session():
    """Create a test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_grading_config(db_session):
    """Test creating a grading configuration."""
    repo = GradingConfigRepository(db_session)
    config = await repo.create(
        external_assignment_id="test-assignment-1", definition=definition()
    )
    assert config.id is not None
    assert config.external_assignment_id == "test-assignment-1"
    assert config.definition["templates"] == ["input_output"]
    assert config.definition["languages"] == ["python"]
    assert config.is_active is True


@pytest.mark.asyncio
async def test_get_config_by_external_id(db_session):
    """Test retrieving config by external assignment ID."""
    repo = GradingConfigRepository(db_session)
    await repo.create(
        external_assignment_id="test-assignment-2", definition=definition()
    )
    config = await repo.get_by_external_id("test-assignment-2")
    assert config is not None
    assert config.external_assignment_id == "test-assignment-2"
    assert config.definition["templates"] == ["input_output"]


@pytest.mark.asyncio
async def test_get_active_configs(db_session):
    """Test getting all active configurations."""
    repo = GradingConfigRepository(db_session)
    await repo.create(external_assignment_id="assignment-1", definition=definition())
    await repo.create(external_assignment_id="assignment-2", definition=definition())
    configs = await repo.get_active_configs()
    assert len(configs) == 2


@pytest.mark.asyncio
async def test_create_submission(db_session):
    """Test creating a submission."""
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-3", definition=definition()
    )
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
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-4", definition=definition()
    )
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
    submissions = await submission_repo.get_by_user("user-456")
    assert len(submissions) == 2


@pytest.mark.asyncio
async def test_update_submission_status(db_session):
    """Test updating submission status."""
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-5", definition=definition()
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
    updated = await submission_repo.update_status(
        submission.id, SubmissionStatus.PROCESSING
    )
    assert updated.status == SubmissionStatus.PROCESSING


@pytest.mark.asyncio
async def test_create_submission_result(db_session):
    """Test creating a submission result."""
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-6", definition=definition()
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
    config_repo = GradingConfigRepository(db_session)
    config = await config_repo.create(
        external_assignment_id="test-assignment-7", definition=definition()
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
    result = await result_repo.get_by_submission_id(submission.id)
    assert result is not None
    assert result.final_score == 90.0
