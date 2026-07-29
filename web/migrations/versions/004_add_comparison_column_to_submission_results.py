"""add comparison column to submission_results

Revision ID: 004
Revises: 003
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add comparison column to submission_results table."""
    op.add_column('submission_results',
                  sa.Column('comparison', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove comparison column from submission_results table."""
    op.drop_column('submission_results', 'comparison')
