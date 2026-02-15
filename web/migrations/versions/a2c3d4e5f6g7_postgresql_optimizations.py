"""PostgreSQL optimizations

Revision ID: a2c3d4e5f6g7
Revises: b1f865312196
Create Date: 2026-02-15 10:00:00.000000

This migration adds PostgreSQL-specific optimizations:
- Adds composite indexes for common query patterns
- Adds partial indexes for active records
- Optimizes ENUM types for PostgreSQL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'b1f865312196'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply PostgreSQL optimizations."""
    # Get bind to check if we're using PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # Skip PostgreSQL-specific optimizations for other databases
        return

    # Add composite index for common query: get submissions by user and config
    op.create_index(
        'ix_submissions_user_config',
        'submissions',
        ['external_user_id', 'grading_config_id'],
        unique=False
    )

    # Add composite index for submissions by config and status
    op.create_index(
        'ix_submissions_config_status',
        'submissions',
        ['grading_config_id', 'status'],
        unique=False
    )

    # Add partial index for active grading configurations (PostgreSQL only)
    op.execute(
        "CREATE INDEX ix_grading_configurations_active "
        "ON grading_configurations (external_assignment_id, template_name) "
        "WHERE is_active = true"
    )

    # Add partial index for pending submissions (PostgreSQL only)
    op.execute(
        "CREATE INDEX ix_submissions_pending "
        "ON submissions (submitted_at DESC) "
        "WHERE status = 'PENDING'"
    )

    # Add index for recent submissions lookup
    op.create_index(
        'ix_submissions_recent',
        'submissions',
        ['submitted_at'],
        unique=False,
        postgresql_ops={'submitted_at': 'DESC'}
    )

    # Add index on submission_results for performance
    op.create_index(
        'ix_submission_results_status',
        'submission_results',
        ['pipeline_status'],
        unique=False
    )


def downgrade() -> None:
    """Remove PostgreSQL optimizations."""
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    # Drop indexes in reverse order
    op.drop_index('ix_submission_results_status', table_name='submission_results')
    op.drop_index('ix_submissions_recent', table_name='submissions')
    op.execute("DROP INDEX IF EXISTS ix_submissions_pending")
    op.execute("DROP INDEX IF EXISTS ix_grading_configurations_active")
    op.drop_index('ix_submissions_config_status', table_name='submissions')
    op.drop_index('ix_submissions_user_config', table_name='submissions')

