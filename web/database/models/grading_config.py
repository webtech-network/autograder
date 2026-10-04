"""Canonical grading definition resource; execution snapshots live on submissions."""

from datetime import datetime
from sqlalchemy import Boolean, Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from web.database.base import Base


class GradingConfiguration(Base):
    __tablename__ = "grading_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_assignment_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    definition_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    migration_error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="grading_config"
    )
