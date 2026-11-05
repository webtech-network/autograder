"""Migrations own the schema; the API only verifies the revision it was built for.

``python -m web.database.schema adopt`` brings a database created by the old
startup ``create_all`` under migrations: it stamps ``ADOPTED_REVISION`` only when the
live schema already equals the models, and otherwise prints the differences.
"""
import argparse
import asyncio
import os
from pathlib import Path
import sys

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from web.database.base import Base
from web.database import models  # noqa: F401  # pylint: disable=unused-import  # Register tables.

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
UPGRADE_COMMAND = "alembic -c web/alembic.ini upgrade head"
# The revision whose schema the old startup ``create_all`` produced. Adoption stamps
# it, never head, so ``upgrade head`` still runs the later revisions, including data
# migrations such as ``009`` (stored outcome text excerpts) that the rows need.
ADOPTED_REVISION = "008"


class SchemaNotCurrent(RuntimeError):
    """The database is not at the revision this build requires."""


def migration_scripts():
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def head_revision():
    return migration_scripts().get_current_head()


def schema_differences(connection, metadata=Base.metadata):
    """Autogenerate operations needed to make the live schema equal ``metadata``."""
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True})
    return compare_metadata(context, metadata)


async def require_current_schema(engine):
    """Refuse to serve unless the database is exactly at this build's head revision."""
    async with engine.connect() as connection:
        current = await connection.run_sync(
            lambda sync: MigrationContext.configure(sync).get_current_revision())
    head = head_revision()
    if current == head:
        return
    if current is None:
        state = "has no migration revision (empty, or created by an older API startup)"
    else:
        state = f"is at revision {current}"
    raise SchemaNotCurrent(
        f"Database schema {state}; this build requires revision {head}. The API never "
        f"creates or alters tables. Run `{UPGRADE_COMMAND}` with the same DATABASE_URL "
        "before starting it. A database created by an older API startup must first be "
        "adopted with `python -m web.database.schema adopt` (docs/contracts/JOBS.md).")


def _adopt(connection):
    context = MigrationContext.configure(connection)
    current = context.get_current_revision()
    if current is not None:
        return False, f"Database is already managed by migrations (revision {current}); run `{UPGRADE_COMMAND}`."
    if not set(Base.metadata.tables) & set(inspect(connection).get_table_names()):
        return False, f"Database has no application tables; create them with `{UPGRADE_COMMAND}`."
    differences = schema_differences(connection)
    if differences:
        listed = "\n".join(f"  {difference}" for difference in differences)
        return False, ("Schema differs from the models, so it cannot be stamped. Reconcile these "
                       f"differences (or restore a migrated backup) and retry:\n{listed}")
    context.stamp(migration_scripts(), ADOPTED_REVISION)
    return True, (f"Schema matches the models; stamped revision {ADOPTED_REVISION}. "
                  f"Run `{UPGRADE_COMMAND}` to apply the later revisions.")


async def adopt(url):
    """Stamp ``ADOPTED_REVISION`` on an unversioned database whose schema equals the models."""
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            return await connection.run_sync(_adopt)
    finally:
        await engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m web.database.schema", description=__doc__)
    parser.add_argument("command", choices=["adopt"])
    parser.parse_args(argv)
    url = os.getenv("DATABASE_URL")
    if not url:
        parser.error("set DATABASE_URL to the database to adopt")
    adopted, message = asyncio.run(adopt(url))
    print(message, file=sys.stdout if adopted else sys.stderr)
    return 0 if adopted else 1


if __name__ == "__main__":
    sys.exit(main())
