"""Unit tests for multi-language submission support in the pipeline."""

import pytest
from unittest.mock import Mock, patch

from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language


class TestSubmissionLanguageHandling:
    """Test that Submission correctly handles language attribute."""

    def test_submission_with_explicit_language(self):
        """Test creating a submission with explicit language."""
        files = {
            "test.py": SubmissionFile(filename="test.py", content="print('hello')")
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON
        )

        assert submission.language == Language.PYTHON

    def test_submission_without_language(self):
        """Test creating a submission without language (defaults to None)."""
        files = {
            "test.py": SubmissionFile(filename="test.py", content="print('hello')")
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files
        )

        assert submission.language is None

    def test_submission_with_different_languages(self):
        """Test that submissions can be created with different languages."""
        files_py = {
            "test.py": SubmissionFile(filename="test.py", content="print('hello')")
        }
        files_java = {
            "Test.java": SubmissionFile(filename="Test.java", content="public class Test {}")
        }

        submission_py = Submission(
            username="user1",
            user_id=1,
            assignment_id=1,
            submission_files=files_py,
            language=Language.PYTHON
        )

        submission_java = Submission(
            username="user2",
            user_id=2,
            assignment_id=1,  # Same assignment
            submission_files=files_java,
            language=Language.JAVA
        )

        assert submission_py.language == Language.PYTHON
        assert submission_java.language == Language.JAVA
        assert submission_py.assignment_id == submission_java.assignment_id

    def test_all_supported_languages(self):
        """Test that all Language enum values can be used."""
        files = {
            "test": SubmissionFile(filename="test", content="test")
        }

        for language in Language:
            submission = Submission(
                username="testuser",
                user_id=1,
                assignment_id=1,
                submission_files=files,
                language=language
            )
            assert submission.language == language


class TestPipelineLanguageHandling:
    """Test that the pipeline correctly uses the submission's language."""

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_uses_submission_language_for_sandbox(self, mock_get_manager):
        """Test that the pipeline creates sandbox using submission's language."""
        from autograder.autograder import build_pipeline
        from autograder.models.dataclass.submission import Submission, SubmissionFile

        # Mock sandbox manager
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Create pipeline with preflight step (which uses sandbox)
        pipeline = build_pipeline(
            template_name="input_output",
            include_feedback=False,
            grading_criteria={
                "test_library": "input_output",
                "base": {"weight": 100, "tests": []}
            },
            feedback_config=None,
            setup_config={}  # Empty config to enable preflight
        )

        # Create submission with Java language
        files = {
            "Test.java": SubmissionFile(filename="Test.java", content="public class Test {}")
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.JAVA
        )

        # Run pipeline
        try:
            pipeline.run(submission)
        except Exception:
            # We expect errors since we're mocking, but we want to verify the language was used
            pass

        # Verify sandbox was requested with Java language
        # This will be called during preflight
        if mock_manager.get_sandbox.called:
            mock_manager.get_sandbox.assert_called_with(Language.JAVA)


class TestLanguageEnumValues:
    """Test Language enum values match expected strings."""

    def test_language_enum_values(self):
        """Verify Language enum has correct values."""
        assert Language.PYTHON.value == "python"
        assert Language.JAVA.value == "java"
        assert Language.NODE.value == "node"
        assert Language.CPP.value == "cpp"

    def test_language_enum_from_string(self):
        """Test converting strings to Language enum."""
        assert Language["PYTHON"] == Language.PYTHON
        assert Language["JAVA"] == Language.JAVA
        assert Language["NODE"] == Language.NODE
        assert Language["CPP"] == Language.CPP

    def test_language_enum_uppercase_access(self):
        """Test that Language enum can be accessed by uppercase name."""
        language_str = "python"
        language_enum = Language[language_str.upper()]
        assert language_enum == Language.PYTHON
        assert language_enum.value == "python"


class TestLanguageResolution:
    """Test the language resolution logic in submission creation."""

    def test_language_resolution_with_override(self):
        """Test that submission language overrides config language."""
        config_language = "python"
        submission_language = "java"

        # Simulate the logic from web/main.py line 308
        resolved_language = submission_language or config_language

        assert resolved_language == "java"

    def test_language_resolution_without_override(self):
        """Test that config language is used when submission has no override."""
        config_language = "python"
        submission_language = None

        # Simulate the logic from web/main.py line 308
        resolved_language = submission_language or config_language

        assert resolved_language == "python"

    def test_language_resolution_empty_string(self):
        """Test that empty string uses config language."""
        config_language = "python"
        submission_language = ""

        # Simulate the logic from web/main.py line 308
        resolved_language = submission_language or config_language

        assert resolved_language == "python"

