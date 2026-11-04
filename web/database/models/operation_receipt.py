"""Replay records for caller-keyed operations (INT-04).

One row binds (authenticated principal, operation, caller key) to the resource the
first request created and a fingerprint of that request. It is written in the
same transaction as the resource, so either both exist or neither does.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from web.database.base import Base


class OperationReceipt(Base):
    __tablename__ = "operation_receipts"
    __table_args__ = (UniqueConstraint("principal", "operation", "idempotency_key",
                                       name="uq_operation_receipts_principal_operation_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal: Mapped[str] = mapped_column(String(80), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
