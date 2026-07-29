"""add score_vector column to submission_results

Revision ID: 003
Revises: 002
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add score_vector column to submission_results table."""
    op.add_column('submission_results',
                  sa.Column('score_vector', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove score_vector column from submission_results table."""
    op.drop_column('submission_results', 'score_vector')
