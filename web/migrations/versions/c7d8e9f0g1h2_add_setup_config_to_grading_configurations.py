"""Add setup_config to grading_configurations

Revision ID: c7d8e9f0g1h2
Revises: a2c3d4e5f6g7
Create Date: 2026-02-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0g1h2'
down_revision: Union[str, Sequence[str], None] = 'a2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add setup_config column to grading_configurations table."""
    # Add the setup_config column as nullable JSON
    op.add_column('grading_configurations',
                  sa.Column('setup_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove setup_config column from grading_configurations table."""
    op.drop_column('grading_configurations', 'setup_config')

