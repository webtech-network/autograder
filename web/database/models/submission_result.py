"""SubmissionResult database model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Integer, Float, Text, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from web.database.base import Base


class PipelineStatus(str, Enum):
    """Status of the grading pipeline execution."""
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class SubmissionResult(Base):
    """
    Stores the outcome of grading a submission.
    
    Persists grading results, feedback, and detailed test outcomes.
    """
    __tablename__ = "submission_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    result_tree: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_execution: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # NEW: Pipeline step details
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    pipeline_status: Mapped[PipelineStatus] = mapped_column(SQLEnum(PipelineStatus), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_at_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="result")

    def __repr__(self):
        return f"<SubmissionResult(id={self.id}, submission_id={self.submission_id}, score={self.final_score})>"
