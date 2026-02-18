"""add focus column to submission results

Revision ID: 001
Revises:
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add focus column to submission_results table
    op.add_column('submission_results',
                  sa.Column('focus', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove focus column from submission_results table
    op.drop_column('submission_results', 'focus')

