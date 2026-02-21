"""Submission database model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from web.database.base import Base


class SubmissionStatus(str, Enum):
    """Status of a submission in the grading pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Submission(Base):
    """
    Represents a student's code submission.
    
    Tracks what was submitted, when, and by whom, providing traceability and audit logs.
    """
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grading_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("grading_configurations.id"), nullable=False, index=True)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    submission_files: Mapped[dict] = mapped_column(JSON, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SQLEnum(SubmissionStatus, values_callable=lambda x: [e.value for e in x]),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submission_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    origin_client_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Relationships
    grading_config: Mapped["GradingConfiguration"] = relationship("GradingConfiguration", back_populates="submissions")
    result: Mapped[Optional["SubmissionResult"]] = relationship("SubmissionResult", back_populates="submission", uselist=False)

    def __repr__(self):
        return f"<Submission(id={self.id}, user={self.username}, status={self.status})>"
