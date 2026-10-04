"""Exercise the actual migration against legacy SQL tables, not new ORM metadata."""

import importlib
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_valid_conversion_invalid_quarantine_and_unverified_history(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    configs = sa.Table(
        "grading_configurations",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("external_assignment_id", sa.String),
        sa.Column("template_name", sa.String),
        sa.Column("criteria_config", sa.JSON),
        sa.Column("languages", sa.JSON),
        sa.Column("setup_config", sa.JSON),
        sa.Column("feedback_config", sa.JSON),
        sa.Column("include_feedback", sa.Boolean),
        sa.Column("version", sa.Integer),
        sa.Column("is_active", sa.Boolean),
    )
    submissions = sa.Table(
        "submissions", metadata, sa.Column("id", sa.Integer, primary_key=True)
    )
    results = sa.Table(
        "submission_results",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("final_score", sa.Float, nullable=False),
        sa.Column("pipeline_status", sa.String),
    )
    metadata.create_all(engine)
    legacy_criteria = {
        "base": {
            "weight": 100,
            "tests": [
                {
                    "type": "expect_output",
                    "name": "Hello",
                    "weight": 1,
                    "parameters": [
                        {"name": "program_command", "value": "python main.py"},
                        {"name": "expected_output", "value": "Hello"},
                    ],
                }
            ],
        }
    }
    with engine.begin() as connection:
        connection.execute(
            configs.insert(),
            [
                {
                    "id": 1,
                    "external_assignment_id": "valid",
                    "template_name": "input_output",
                    "criteria_config": legacy_criteria,
                    "languages": ["python"],
                    "setup_config": None,
                    "feedback_config": None,
                    "include_feedback": False,
                    "version": 1,
                    "is_active": True,
                },
                {
                    "id": 2,
                    "external_assignment_id": "invalid",
                    "template_name": "input_output",
                    "criteria_config": {"base": {"weight": 100, "tests": []}},
                    "languages": ["python"],
                    "setup_config": None,
                    "feedback_config": None,
                    "include_feedback": False,
                    "version": 1,
                    "is_active": True,
                },
            ],
        )
        connection.execute(submissions.insert(), {"id": 1})
        connection.execute(
            results.insert(),
            [
                {"id": 1, "final_score": 0, "pipeline_status": "failed"},
                {"id": 2, "final_score": 80, "pipeline_status": "success"},
            ],
        )
        migration = importlib.import_module(
            "web.migrations.versions.005_canonical_contracts"
        )
        monkeypatch.setattr(
            migration, "op", Operations(MigrationContext.configure(connection))
        )
        migration.upgrade()
        converted = sa.Table(
            "grading_configurations", sa.MetaData(), autoload_with=connection
        )
        valid, invalid = (
            connection.execute(sa.select(converted).order_by(converted.c.id))
            .mappings()
            .all()
        )
        assert valid["definition"]["schema_version"] == "1.0"
        assert len(valid["definition_hash"]) == 64 and valid["is_active"]
        assert invalid["definition"] is None and not invalid["is_active"]
        assert invalid["migration_error"]["errors"]
        assert invalid["migration_error"]["legacy_definition"]["criteria_config"] == {
            "base": {"weight": 100, "tests": []}
        }
        assert "criteria_config" not in converted.c
        historic = connection.execute(
            sa.text(
                "SELECT definition_snapshot,definition_hash,configuration_version FROM submissions"
            )
        ).one()
        assert tuple(historic) == (None, None, None)
        old_results = connection.execute(
            sa.text("SELECT final_score,outcome FROM submission_results ORDER BY id")
        ).all()
        assert old_results == [(None, None), (80, None)]
