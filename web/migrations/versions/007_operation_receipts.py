"""Caller-keyed replay receipts for acceptance and attestation (INT-04)."""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operation_receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("principal", sa.String(80), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("submission_id", sa.Integer(),
                  sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("principal", "operation", "idempotency_key",
                            name="uq_operation_receipts_principal_operation_key"),
    )
    op.create_index("ix_operation_receipts_submission_id", "operation_receipts", ["submission_id"])


def downgrade():
    op.drop_index("ix_operation_receipts_submission_id", table_name="operation_receipts")
    op.drop_table("operation_receipts")
