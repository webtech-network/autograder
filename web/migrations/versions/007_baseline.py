# pylint: disable=invalid-name
"""Baseline: the schema that revisions 001-007 produced, created from empty.

Revisions 001-007 could not run on an empty database: they altered tables that
only the API's startup ``create_all`` created. They are squashed into this one
root revision. It keeps the identifier ``007`` so a database already at ``007``
needs no action, and it reproduces that database exactly (naive timestamps and
backfill defaults included); revision ``008`` then brings both to the models.

A database at ``001``-``006`` must first upgrade to ``007`` with a release that
still contains the old chain (commit 3a8abcc), as described in
docs/contracts/JOBS.md.
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = None
branch_labels = None
depends_on = None

SUBMISSION_STATUS = sa.Enum("pending", "processing", "completed", "failed", name="submissionstatus")
PIPELINE_STATUS = sa.Enum("success", "failed", "interrupted", name="pipelinestatus")


def upgrade():
    op.create_table(
        "grading_configurations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_assignment_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=True),
        sa.Column("definition_hash", sa.String(64), nullable=True),
        sa.Column("migration_error", sa.JSON(), nullable=True),
    )
    op.create_index("ix_grading_configurations_external_assignment_id", "grading_configurations",
                    ["external_assignment_id"], unique=True)

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("grading_config_id", sa.Integer(), sa.ForeignKey("grading_configurations.id"), nullable=False),
        sa.Column("external_user_id", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("submission_files", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("status", SUBMISSION_STATUS, nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("graded_at", sa.DateTime(), nullable=True),
        sa.Column("submission_metadata", sa.JSON(), nullable=True),
        sa.Column("definition_snapshot", sa.JSON(), nullable=True),
        sa.Column("definition_hash", sa.String(64), nullable=True),
        sa.Column("configuration_version", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(32), server_default="en", nullable=False),
        sa.Column("evaluation_scope", sa.JSON(), nullable=True),
        sa.Column("attempt_id", sa.String(36), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("grading_config_id", "external_user_id", "status", "submitted_at", "lease_until"):
        op.create_index(f"ix_submissions_{column}", "submissions", [column])

    op.create_table(
        "submission_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("result_tree", sa.JSON(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("pipeline_execution", sa.JSON(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("pipeline_status", PIPELINE_STATUS, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("failed_at_step", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("focus", sa.JSON(), nullable=True),
        sa.Column("score_vector", sa.JSON(), nullable=True),
        sa.Column("comparison", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.JSON(), nullable=True),
        sa.Column("diagnostics", sa.JSON(), nullable=True),
    )
    op.create_index("ix_submission_results_submission_id", "submission_results", ["submission_id"], unique=True)

    op.create_table(
        "grading_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_grading_attempts_submission_id", "grading_attempts", ["submission_id"])

    op.create_table(
        "operation_receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("principal", sa.String(80), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("principal", "operation", "idempotency_key",
                            name="uq_operation_receipts_principal_operation_key"),
    )
    op.create_index("ix_operation_receipts_submission_id", "operation_receipts", ["submission_id"])


def downgrade():
    for table in ("operation_receipts", "grading_attempts", "submission_results", "submissions",
                  "grading_configurations"):
        op.drop_table(table)
    # PostgreSQL keeps enum types after their tables; other dialects have none.
    PIPELINE_STATUS.drop(op.get_bind(), checkfirst=True)
    SUBMISSION_STATUS.drop(op.get_bind(), checkfirst=True)
