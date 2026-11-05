# pylint: disable=invalid-name
"""Align the migrated schema with the models that startup create_all used to apply.

Timestamps the models declare timezone-aware were naive in migrated databases,
so reads depended on the session time zone. Stored naive values are read as UTC:
the API writes UTC, and the ``now()`` defaults use the database ``TimeZone``,
which is UTC in the supported images. The
``locale`` and ``attempt_count`` defaults only backfilled rows when ``006``
added the columns; the application always writes both.
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

TIMESTAMPS = {
    "grading_configurations": (("created_at", False), ("updated_at", False)),
    "submissions": (("submitted_at", False), ("graded_at", True)),
}
BACKFILL_DEFAULTS = (("locale", sa.String(32), "en"), ("attempt_count", sa.Integer(), "0"))


def _convert_timestamps(timezone):
    for table, columns in TIMESTAMPS.items():
        with op.batch_alter_table(table) as batch:
            for column, nullable in columns:
                batch.alter_column(
                    column, existing_type=sa.DateTime(timezone=not timezone),
                    type_=sa.DateTime(timezone=timezone), existing_nullable=nullable,
                    postgresql_using=f"{column} AT TIME ZONE 'UTC'")


def upgrade():
    _convert_timestamps(timezone=True)
    with op.batch_alter_table("submissions") as batch:
        for column, type_, _ in BACKFILL_DEFAULTS:
            batch.alter_column(column, existing_type=type_, existing_nullable=False, server_default=None)


def downgrade():
    with op.batch_alter_table("submissions") as batch:
        for column, type_, default in BACKFILL_DEFAULTS:
            batch.alter_column(column, existing_type=type_, existing_nullable=False, server_default=default)
    _convert_timestamps(timezone=False)
