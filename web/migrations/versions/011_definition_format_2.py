"""Store every definition the API still grades in format 2.0 (ONB-07).

The engine reads only format 2.0. Each 1.0 definition it would still grade is
converted by the offline converter's snapshot path (``convert_snapshot``):
fields are renamed, no parameter value is normalized again, and the result is
validated exactly as a stored snapshot is loaded.

* ``grading_configurations``: a converted definition becomes a new revision
  (``version + 1``) with its new hash, so a revision never names two hashes.
  A definition that does not convert is quarantined: inactive, ``definition``
  and hash cleared, and ``migration_error`` holding the 1.0 definition with the
  exact errors; PATCH a corrected definition, then reactivate it.
* ``submissions`` that are still queued (pending or processing) are rebound to
  the converted snapshot and its hash; they keep their revision. One that does
  not convert is left as it was and fails with its validation error when graded,
  as it would have before.
* Finished submissions keep their 1.0 snapshot, hash and outcome untouched: the
  outcome's provenance (``schema_version`` 1.0) still verifies against it.

Running the upgrade again changes nothing. Downgrade refuses while any 2.0
definition is stored, since the previous release cannot read one: roll back by
restoring the backup taken before the upgrade, together with the previous
release (docs/contracts/DECISIONS.md, migration notes).
"""
from datetime import datetime, timezone
import logging

from alembic import op
import sqlalchemy as sa

from autograder.models.contracts.definition import DefinitionValidationError, SCHEMA_VERSION, snapshot_hash
from autograder.services.definition_migration import convert_snapshot

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

_QUEUED = ("pending", "processing")

configurations = sa.table(
    "grading_configurations", sa.column("id", sa.Integer), sa.column("definition", sa.JSON),
    sa.column("definition_hash", sa.String), sa.column("migration_error", sa.JSON),
    sa.column("version", sa.Integer), sa.column("is_active", sa.Boolean),
    sa.column("updated_at", sa.DateTime(timezone=True)))
submissions = sa.table(
    "submissions", sa.column("id", sa.Integer), sa.column("status", sa.String),
    sa.column("definition_snapshot", sa.JSON), sa.column("definition_hash", sa.String))


def _convert(snapshot, where):
    """``(definition, hash)`` of a stored 1.0 snapshot in format 2.0, or the conversion errors."""
    try:
        converted = convert_snapshot(snapshot)
    except DefinitionValidationError as exc:
        return None, exc.errors()
    for note in converted.notes:
        logger.warning("%s: %s at %s", where, note["message"], ".".join(map(str, note["path"])))
    return converted.definition, snapshot_hash(converted.definition)


def _queued():
    # The status column is a PostgreSQL enum: compare its text, which every dialect has.
    return sa.cast(submissions.c.status, sa.String).in_(_QUEUED)


def _is_v1(value):
    return isinstance(value, dict) and value.get("schema_version") == "1.0"


def upgrade():
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = connection.execute(sa.select(configurations.c.id, configurations.c.definition, configurations.c.version)
                              .order_by(configurations.c.id)).all()
    for row in rows:
        if not _is_v1(row.definition):
            continue
        definition, result = _convert(row.definition, f"grading_configurations.id={row.id}")
        if definition is not None:
            values = {"definition": definition, "definition_hash": result}
        else:
            logger.warning("grading_configurations.id=%s quarantined: %s", row.id, result)
            values = {"definition": None, "definition_hash": None, "is_active": False,
                      "migration_error": {"schema_version": "1.0", "definition": row.definition, "errors": result}}
        connection.execute(configurations.update().where(configurations.c.id == row.id)
                           .values(**values, version=row.version + 1, updated_at=now))

    queued = connection.execute(sa.select(submissions.c.id, submissions.c.definition_snapshot)
                                .where(_queued()).order_by(submissions.c.id)).all()
    for row in queued:
        if not _is_v1(row.definition_snapshot):
            continue
        definition, result = _convert(row.definition_snapshot, f"submissions.id={row.id}")
        if definition is None:
            logger.warning("submissions.id=%s keeps its 1.0 snapshot and will fail when graded: %s", row.id, result)
            continue
        connection.execute(submissions.update().where(submissions.c.id == row.id)
                           .values(definition_snapshot=definition, definition_hash=result))


def downgrade():
    """Refuse to hand 2.0 definitions to a release that cannot read them."""
    connection = op.get_bind()
    stored = [value for (value,) in connection.execute(sa.select(configurations.c.definition))]
    stored += [value for (value,) in connection.execute(
        sa.select(submissions.c.definition_snapshot).where(_queued()))]
    if any(isinstance(value, dict) and value.get("schema_version") == SCHEMA_VERSION for value in stored):
        raise RuntimeError(
            f"Definitions in format {SCHEMA_VERSION} are stored, and the previous release reads only 1.0. "
            "Roll back by restoring the database backup taken before upgrading to revision 011, "
            "together with the previous release.")
