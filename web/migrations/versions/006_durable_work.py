"""Persist replayable input and fence bounded worker attempts."""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("submissions", sa.Column("locale", sa.String(32), nullable=False, server_default="en"))
    op.add_column("submissions", sa.Column("evaluation_scope", sa.JSON(), nullable=True))
    op.add_column("submissions", sa.Column("attempt_id", sa.String(36), nullable=True))
    op.add_column("submissions", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("submissions", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_submissions_lease_until", "submissions", ["lease_until"])
    op.create_table(
        "grading_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_grading_attempts_submission_id", "grading_attempts", ["submission_id"])
    # Existing pending/processing rows omitted scope and locale. Never fabricate
    # replay provenance: only newly accepted complete input is worker eligible.
    op.execute("UPDATE submissions SET status = 'failed' WHERE status IN ('pending', 'processing')")


def downgrade():
    op.drop_table("grading_attempts")
    op.drop_index("ix_submissions_lease_until", table_name="submissions")
    for name in ("lease_until", "attempt_count", "attempt_id", "evaluation_scope", "locale"):
        op.drop_column("submissions", name)
