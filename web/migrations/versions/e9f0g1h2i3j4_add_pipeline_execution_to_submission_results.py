"""Add pipeline_execution to submission_results

Revision ID: e9f0g1h2i3j4
Revises: c7d8e9f0g1h2
Create Date: 2026-02-17 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f0g1h2i3j4'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0g1h2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pipeline_execution column to submission_results table."""
    op.add_column('submission_results',
                  sa.Column('pipeline_execution', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove pipeline_execution column from submission_results table."""
    op.drop_column('submission_results', 'pipeline_execution')

