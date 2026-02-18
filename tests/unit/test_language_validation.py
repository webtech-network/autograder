"""Tests for language validation in schemas."""

import pytest
from pydantic import ValidationError

from web.schemas.assignment import GradingConfigCreate, GradingConfigUpdate
from web.schemas.submission import SubmissionCreate, SubmissionFileData


class TestLanguageValidation:
    """Test language validation in configuration and submission schemas."""

    def test_grading_config_create_valid_languages(self):
        """Test that valid languages are accepted in GradingConfigCreate."""
        valid_languages = ["python", "java", "node", "cpp", "PYTHON", "Java", "NODE", "Cpp"]

        for lang in valid_languages:
            config = GradingConfigCreate(
                external_assignment_id="test-001",
                template_name="input_output",
                criteria_config={"test_library": "input_output"},
                language=lang
            )
            # Should normalize to lowercase
            assert config.language in ["python", "java", "node", "cpp"]

    def test_grading_config_create_invalid_language(self):
        """Test that invalid languages are rejected in GradingConfigCreate."""
        with pytest.raises(ValidationError) as exc_info:
            GradingConfigCreate(
                external_assignment_id="test-001",
                template_name="input_output",
                criteria_config={"test_library": "input_output"},
                language="javascript"  # Should be "node"
            )

        error = exc_info.value.errors()[0]
        assert "language" in error["loc"]
        assert "Unsupported language" in error["msg"]
        assert "javascript" in error["msg"]

    def test_grading_config_create_empty_language(self):
        """Test that empty language is rejected in GradingConfigCreate."""
        with pytest.raises(ValidationError) as exc_info:
            GradingConfigCreate(
                external_assignment_id="test-001",
                template_name="input_output",
                criteria_config={"test_library": "input_output"},
                language=""
            )

        error = exc_info.value.errors()[0]
        assert "language" in error["loc"]
        assert "cannot be empty" in error["msg"].lower()

    def test_grading_config_create_unsupported_languages(self):
        """Test that various unsupported languages are rejected."""
        unsupported = ["ruby", "go", "rust", "c", "csharp", "php", "perl"]

        for lang in unsupported:
            with pytest.raises(ValidationError) as exc_info:
                GradingConfigCreate(
                    external_assignment_id="test-001",
                    template_name="input_output",
                    criteria_config={"test_library": "input_output"},
                    language=lang
                )

            error = exc_info.value.errors()[0]
            assert "language" in error["loc"]
            assert "Unsupported language" in error["msg"]

    def test_grading_config_update_valid_language(self):
        """Test that valid language is accepted in GradingConfigUpdate."""
        update = GradingConfigUpdate(language="python")
        assert update.language == "python"

    def test_grading_config_update_invalid_language(self):
        """Test that invalid language is rejected in GradingConfigUpdate."""
        with pytest.raises(ValidationError) as exc_info:
            GradingConfigUpdate(language="javascript")

        error = exc_info.value.errors()[0]
        assert "language" in error["loc"]
        assert "Unsupported language" in error["msg"]

    def test_grading_config_update_none_language(self):
        """Test that None language is accepted in GradingConfigUpdate."""
        update = GradingConfigUpdate(language=None)
        assert update.language is None

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

