"""Tests for ForbiddenKeywordTest."""

from tests.evaluator_calls import invoke

PARSE = "autograder.template_library.static_analysis.parse_source"
from unittest.mock import MagicMock, patch
import pytest
from autograder.models.evaluation_error import EvaluationError

from autograder.template_library.static_analysis import ForbiddenKeywordTest, StaticAnalysisTemplate, ForbiddenKeywordConfig
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.models.sandbox_models import Language


class TestForbiddenKeywordRegistration:
    """Test that ForbiddenKeywordTest is properly registered in the template."""

    def test_forbidden_keyword_registered_in_template(self):
        """Test that the forbidden_keyword test is available in StaticAnalysisTemplate."""
        template = StaticAnalysisTemplate()
        test = template.get_test("forbidden_keyword")
        assert test is not None
        assert test.name == "forbidden_keyword"


class TestForbiddenKeywordConfig:
    """Test ForbiddenKeywordConfig validation."""

    def test_valid_config(self):
        """Test with valid parameters."""
        config = ForbiddenKeywordConfig(
            forbidden_keywords=["for_loop"],
            custom_ast_grep_rules=[{"kind": "if_statement"}]
        )
        assert config.forbidden_keywords == ["for_loop"]
        assert config.custom_ast_grep_rules == [{"kind": "if_statement"}]

    def test_empty_config(self):
        """Test with empty parameters."""
        config = ForbiddenKeywordConfig()
        assert config.forbidden_keywords == []
        assert config.custom_ast_grep_rules == []


class TestForbiddenKeywordMetadata:
    """Test ForbiddenKeywordTest metadata and properties."""

    test_fn: ForbiddenKeywordTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenKeywordTest()

    def test_name(self):
        """Test that the test name is 'forbidden_keyword'."""
        assert self.test_fn.name == "forbidden_keyword"

    def test_description_not_empty(self):
        """Test that the description is not empty."""
        assert len(self.test_fn.description) > 0

    def test_parameter_descriptions(self):
        """Parameter documentation comes from the contract field descriptions."""
        properties = self.test_fn.config_schema.model_json_schema()["properties"]
        assert list(properties) == ["forbidden_keywords", "custom_ast_grep_rules"]
        assert all(field["description"] for field in properties.values())


class TestForbiddenKeywordExecution:
    """Test execution logic for ForbiddenKeywordTest."""

    test_fn: ForbiddenKeywordTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenKeywordTest()

    def test_no_rules_gives_100(self):
        """Test that no keywords or rules returns full score."""
        result = invoke(self.test_fn, [], None)
        assert result.score == 100.0

    def test_no_analysis_gives_0(self):
        """Test that missing structural analysis returns score 0."""
        with pytest.raises(EvaluationError):
            invoke(self.test_fn, [], None, forbidden_keywords=["for_loop"])

    def test_unavailable_analysis_gives_0(self):
        """Unavailable structural analysis should fail explicitly."""
        parser = patch(PARSE, side_effect=EvaluationError("CAPABILITY_UNAVAILABLE", "Unavailable", "capability"))
        with parser, pytest.raises(EvaluationError):
            invoke(self.test_fn,
                [SubmissionFile("main.py", "for i in range(10): pass")],
                None,
                forbidden_keywords=["for_loop"],
                submission_language=Language.PYTHON,
            )

    def test_no_language_gives_0(self):
        """Test that missing language returns score 0."""
        with pytest.raises(EvaluationError):
            invoke(self.test_fn, [], None,
                                         forbidden_keywords=["for_loop"])

    def test_no_files_gives_100(self):
        """Test that empty file list returns full score."""
        result = invoke(self.test_fn, [], None,
                                     forbidden_keywords=["for_loop"],
                                     submission_language=Language.PYTHON)
        assert result.score == 100.0

    def test_violation_found(self):
        """Test that finding a violation returns score 0."""
        # Mock ast-grep root and matches
        mock_root = MagicMock()
        mock_match = MagicMock()
        mock_root.root().find_all.return_value = [mock_match]

        parser = patch(PARSE, return_value=mock_root)
        files = [SubmissionFile("main.py", "for i in range(10): pass")]
        
        with parser:
            result = invoke(self.test_fn, files, None,
                                     forbidden_keywords=["for_loop"],
                                     submission_language=Language.PYTHON)
        
        assert result.score == 0.0
        assert "main.py" in result.report
        assert "for_statement" in result.report  # The 'kind' for for_loop in Python

    def test_custom_rule_violation(self):
        """Test that a custom ast-grep rule violation returns score 0."""
        mock_root = MagicMock()
        mock_root.root().find_all.return_value = [MagicMock()]

        parser = patch(PARSE, return_value=mock_root)
        files = [SubmissionFile("main.py", "if True: pass")]
        custom_rules = [{"kind": "if_statement"}]
        
        with parser:
            result = invoke(self.test_fn, files, None,
                                     custom_ast_grep_rules=custom_rules,
                                     submission_language=Language.PYTHON)
        
        assert result.score == 0.0
        assert "if_statement" in result.report

    def test_no_violation_found(self):
        """Test that no violations returns full score."""
        mock_root = MagicMock()
        mock_root.root().find_all.return_value = []

        parser = patch(PARSE, return_value=mock_root)
        files = [SubmissionFile("main.py", "x = 1")]
        
        with parser:
            result = invoke(self.test_fn, files, None,
                                     forbidden_keywords=["for_loop"],
                                     submission_language=Language.PYTHON)
        
        assert result.score == 100.0

    def test_missing_roots_for_target_file_gives_0(self):
        """If target files have no parsed roots, the test should fail as no-analysis."""
        parser = patch(PARSE, side_effect=EvaluationError("CAPABILITY_UNAVAILABLE", "Unavailable", "capability"))
        files = [SubmissionFile("main.py", "for i in range(10): pass")]
        with parser, pytest.raises(EvaluationError):
            invoke(self.test_fn,
                files,
                None,
                forbidden_keywords=["for_loop"],
                submission_language=Language.PYTHON,
            )
