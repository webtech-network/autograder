"""Remember which request accepted each submission (#489).

``submissions.request_id`` is the accepting request's ``X-Request-ID`` and
``submissions.traceparent`` the W3C trace context of the API span that accepted
it (only when that span was sampled). The durable worker logs the request id on
every line of the submission's attempts and links each attempt's trace to that
span, so worker and sandbox-manager lines and spans lead back to the request.

Both are nullable and never backfilled: earlier submissions have no recorded
request, and their attempts log the attempt id as the request id. Downgrade
drops both columns; the previous release does not read them.
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("request_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("traceparent", sa.String(55), nullable=True))


def downgrade():
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("traceparent")
        batch.drop_column("request_id")
