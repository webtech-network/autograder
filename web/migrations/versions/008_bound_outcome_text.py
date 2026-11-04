"""Excerpt stored outcome reports and feedback to the outcome text bounds (COR-06).

Before COR-06 an I/O failure stored whole process streams (up to about 1 MiB)
in each criterion report. The outcome contract now bounds reports to 8 KiB and
feedback to 256 KiB, and the same contract validates stored outcomes when they
are served (``/details``) or compared. Every stored outcome is rewritten with
the engine's own ``bound_text`` excerpt, so it reads exactly as if it had been
produced today. Scores, identities and text within a bound are untouched, and
running the upgrade again changes nothing.

Downgrade keeps the excerpts: the previous release accepts every value written
here, and the omitted text is not recoverable.
"""
from alembic import op
import sqlalchemy as sa

from autograder.models.contracts.outcome import bound_outcome_text

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

# Pre-COR-06 rows can be several MiB each; read them a page at a time.
_PAGE = 100


def upgrade():
    connection = op.get_bind()
    results = sa.table("submission_results", sa.column("id", sa.Integer), sa.column("outcome", sa.JSON))
    last = 0
    while True:
        page = connection.execute(
            sa.select(results.c.id, results.c.outcome).where(results.c.id > last)
            .order_by(results.c.id).limit(_PAGE)).all()
        if not page:
            return
        for row in page:
            bounded = bound_outcome_text(row.outcome)
            if bounded != row.outcome:
                connection.execute(results.update().where(results.c.id == row.id).values(outcome=bounded))
        last = page[-1].id


def downgrade():
    """Nothing to undo: excerpts are valid outcome text for the previous release."""
