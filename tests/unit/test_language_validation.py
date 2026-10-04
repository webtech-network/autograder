"""Tests for language validation in schemas."""

import pytest
from pydantic import ValidationError

from web.schemas.assignment import GradingConfigCreate, GradingConfigUpdate
from web.schemas.submission import (
    EvaluationScopeData,
    SubmissionCreate,
    SubmissionFileData,
)


class TestLanguageValidation:
    """Test language validation in configuration and submission schemas."""

    @pytest.mark.parametrize("language", ["python","java","node","cpp","c"])
    def test_grading_config_create_valid_languages(self,language):
        definition={"schema_version":"1.0","templates":["static_analysis"],"languages":[language],
            "criteria":{"base":{"weight":100,"tests":[{"id":"imports","type":"forbidden_import",
                "name":"Imports","parameters":{"forbidden_imports":[]}}]}}}
        config=GradingConfigCreate(external_assignment_id="test-001",definition=definition)
        assert config.definition.languages==[language]

    @pytest.mark.parametrize("language", ["Python","javascript","ruby","","go"])
    def test_grading_config_rejects_noncanonical_languages(self,language):
        definition={"schema_version":"1.0","templates":["static_analysis"],"languages":[language],
            "criteria":{"base":{"weight":100,"tests":[{"id":"imports","type":"forbidden_import",
                "name":"Imports","parameters":{}}]}}}
        with pytest.raises(ValidationError) as failure:
            GradingConfigCreate(external_assignment_id="test-001",definition=definition)
        assert any(error['loc']==('definition','languages',0) for error in failure.value.errors())

    def test_partial_update_omits_definition_but_rejects_explicit_null(self):
        assert GradingConfigUpdate(is_active=False).model_fields_set=={'is_active'}
        with pytest.raises(ValidationError):
            GradingConfigUpdate(definition=None)
        with pytest.raises(ValidationError):
            GradingConfigUpdate(languages=['python'])

    def test_submission_create_valid_language(self):
        """Test that valid language is accepted in SubmissionCreate."""
        submission = SubmissionCreate(
            external_assignment_id="test-001",
            external_user_id="user-001",
            username="testuser",
            files=[SubmissionFileData(filename="test.py", content="print('hello')")],
            language="python"
        )
        assert submission.language == "python"

    def test_submission_create_invalid_language(self):
        """Test that invalid language is rejected in SubmissionCreate."""
        with pytest.raises(ValidationError) as exc_info:
            SubmissionCreate(
                external_assignment_id="test-001",
                external_user_id="user-001",
                username="testuser",
                files=[SubmissionFileData(filename="test.js", content="console.log('hello')")],
                language="javascript"  # Should be "node"
            )

        error = exc_info.value.errors()[0]
        assert "language" in error["loc"]
        assert "Unsupported language" in error["msg"]

    def test_submission_create_none_language(self):
        """Test that None language is accepted in SubmissionCreate."""
        submission = SubmissionCreate(
            external_assignment_id="test-001",
            external_user_id="user-001",
            username="testuser",
            files=[SubmissionFileData(filename="test.py", content="print('hello')")],
            language=None
        )
        assert submission.language is None

    def test_submission_create_case_insensitive(self):
        """Test that language validation is case-insensitive."""
        variations = ["Python", "PYTHON", "PyThOn", "python"]

        for lang in variations:
            submission = SubmissionCreate(
                external_assignment_id="test-001",
                external_user_id="user-001",
                username="testuser",
                files=[SubmissionFileData(filename="test.py", content="print('hello')")],
                language=lang
            )
            assert submission.language == "python"

    def test_submission_create_accepts_evaluation_context(self):
        """Submission schemas accept typed scope and per-file context."""
        submission = SubmissionCreate(
            external_assignment_id="test-001",
            external_user_id="user-001",
            username="testuser",
            files=[
                SubmissionFileData(
                    filename="test.py",
                    content="print('hello')",
                    changed_lines=[1],
                    file_metadata={"change_status": "modified"},
                )
            ],
            evaluation_scope=EvaluationScopeData(scoped_files=["test.py"]),
        )

        assert submission.files[0].changed_lines == [1]
        assert submission.files[0].file_metadata == {"change_status": "modified"}
        assert submission.evaluation_scope.scoped_files == ["test.py"]
