"""GradingConfiguration database model."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from web.database.base import Base


class GradingConfiguration(Base):
    """
    Stores grading criteria configuration for assignments.
    
    This model stores the stateless grading criteria that defines how to grade
    submissions. External systems reference this when students submit code.
    """
    __tablename__ = "grading_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_assignment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    criteria_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    languages: Mapped[list] = mapped_column(JSON, nullable=False)  # List of supported languages
    setup_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="grading_config")

    def __repr__(self):
        return f"<GradingConfiguration(id={self.id}, external_id={self.external_assignment_id}, template={self.template_name})>"
