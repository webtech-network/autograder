# pylint: disable=invalid-name
"""add feedback columns to grading config

Revision ID: 002
Revises: 001
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# pylint: disable=invalid-name
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None
# pylint: enable=invalid-name


def upgrade() -> None:
    """Add feedback columns to grading_configurations table."""
    # Add feedback columns to grading_configurations table
    op.add_column('grading_configurations',
                  sa.Column('feedback_config', sa.JSON(), nullable=True))
    op.add_column('grading_configurations',
                  sa.Column('include_feedback', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    """Remove feedback columns from grading_configurations table."""
    # Remove feedback columns from grading_configurations table
    op.drop_column('grading_configurations', 'include_feedback')
    op.drop_column('grading_configurations', 'feedback_config')
