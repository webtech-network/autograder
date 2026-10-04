"""Canonical definitions, immutable execution snapshots, and terminal outcomes.

Legacy definitions are converted once; rejected rows are quarantined with errors.
Historical executions deliberately remain without snapshots/provenance.
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    from autograder.models.contracts.definition import compile_definition
    from autograder.services.definition_migration import convert_legacy_definition

    op.add_column(
        "grading_configurations", sa.Column("definition", sa.JSON(), nullable=True)
    )
    op.add_column(
        "grading_configurations",
        sa.Column("definition_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "grading_configurations", sa.Column("migration_error", sa.JSON(), nullable=True)
    )
    connection = op.get_bind()
    legacy = sa.Table("grading_configurations", sa.MetaData(), autoload_with=connection)
    for row in connection.execute(sa.select(legacy)).mappings():
        try:
            definition = convert_legacy_definition(
                {
                    "template_name": row["template_name"],
                    "grading_criteria": row["criteria_config"],
                    "languages": row["languages"],
                    "setup_config": row["setup_config"],
                    "feedback_config": row["feedback_config"],
                    "include_feedback": row["include_feedback"],
                }
            )
            compiled = compile_definition(definition)
            values = {
                "definition": compiled.definition.model_dump(mode="json"),
                "definition_hash": compiled.definition_hash,
            }
        except Exception as exc:
            # Preserve conversion evidence; no invalid definition enters the live execution path.
            errors = (
                exc.errors()
                if hasattr(exc, "errors")
                else [{"code": "migration_failed", "path": [], "message": str(exc)}]
            )
            errors = [
                {
                    "code": error.get("code", error.get("type", "MIGRATION_FAILED")),
                    "path": list(error.get("path", error.get("loc", []))),
                    "message": error.get(
                        "message",
                        error.get("msg", "Legacy definition conversion failed"),
                    ),
                }
                for error in errors
            ]
            values = {
                "is_active": False,
                "migration_error": {
                    "errors": errors,
                    "legacy_definition": {
                        key: row[key]
                        for key in (
                            "template_name",
                            "criteria_config",
                            "languages",
                            "setup_config",
                            "feedback_config",
                            "include_feedback",
                        )
                    },
                },
            }
        connection.execute(
            legacy.update().where(legacy.c.id == row["id"]).values(**values)
        )
    with op.batch_alter_table("grading_configurations") as batch:
        for name in (
            "template_name",
            "criteria_config",
            "languages",
            "setup_config",
            "feedback_config",
            "include_feedback",
        ):
            batch.drop_column(name)
    op.add_column(
        "submissions", sa.Column("definition_snapshot", sa.JSON(), nullable=True)
    )
    op.add_column(
        "submissions", sa.Column("definition_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "submissions", sa.Column("configuration_version", sa.Integer(), nullable=True)
    )
    op.add_column("submission_results", sa.Column("outcome", sa.JSON(), nullable=True))
    op.add_column(
        "submission_results", sa.Column("diagnostics", sa.JSON(), nullable=True)
    )
    with op.batch_alter_table("submission_results") as batch:
        batch.alter_column("final_score", existing_type=sa.Float(), nullable=True)
    # Old failed numeric zero is not an authoritative grade.
    connection.execute(
        sa.text(
            "UPDATE submission_results SET final_score = NULL WHERE pipeline_status != 'success'"
        )
    )


def downgrade():
    raise RuntimeError(
        "Canonical contract migration is intentionally irreversible; restore the pre-migration backup"
    )
