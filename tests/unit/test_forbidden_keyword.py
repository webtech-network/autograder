"""Tests for ForbiddenKeywordTest."""

from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from autograder.template_library.input_output import ForbiddenKeywordTest, InputOutputTemplate, ForbiddenKeywordConfig
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
from sandbox_manager.models.sandbox_models import Language


class TestForbiddenKeywordRegistration:
    """Test that ForbiddenKeywordTest is properly registered in the template."""

    def test_forbidden_keyword_registered_in_template(self):
        """Test that the forbidden_keyword test is available in InputOutputTemplate."""
        template = InputOutputTemplate()
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
        """Test that the test has correct parameter descriptions."""
        params = self.test_fn.parameter_description
        assert len(params) == 2
        assert params[0].name == "forbidden_keywords"
        assert params[1].name == "custom_ast_grep_rules"


class TestForbiddenKeywordExecution:
    """Test execution logic for ForbiddenKeywordTest."""

    test_fn: ForbiddenKeywordTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenKeywordTest()

    def test_no_rules_gives_100(self):
        """Test that no keywords or rules returns full score."""
        result = self.test_fn.execute([], None)
        assert result.score == 100.0

    def test_no_analysis_gives_0(self):
        """Test that missing structural analysis returns score 0."""
        result = self.test_fn.execute([], None, forbidden_keywords=["for_loop"])
        assert result.score == 0.0
        assert "analysis" in result.report.lower()

    def test_no_language_gives_0(self):
        """Test that missing language returns score 0."""
        sa_result = StructuralAnalysisResult(roots={})
        result = self.test_fn.execute([], None, 
                                     forbidden_keywords=["for_loop"],
                                     structural_analysis=sa_result)
        assert result.score == 0.0
        assert "language" in result.report.lower()

    def test_no_files_gives_100(self):
        """Test that empty file list returns full score."""
        sa_result = StructuralAnalysisResult(roots={})
        result = self.test_fn.execute([], None,
                                     forbidden_keywords=["for_loop"],
                                     structural_analysis=sa_result,
                                     submission_language=Language.PYTHON)
        assert result.score == 100.0

    def test_violation_found(self):
        """Test that finding a violation returns score 0."""
        # Mock ast-grep root and matches
        mock_root = MagicMock()
        mock_match = MagicMock()
        mock_root.root().find_all.return_value = [mock_match]

        sa_result = StructuralAnalysisResult(roots={"main.py": mock_root})
        files = [SubmissionFile("main.py", "for i in range(10): pass")]
        
        result = self.test_fn.execute(files, None,
                                     forbidden_keywords=["for_loop"],
                                     structural_analysis=sa_result,
                                     submission_language=Language.PYTHON)
        
        assert result.score == 0.0
        assert "main.py" in result.report
        assert "for_statement" in result.report  # The 'kind' for for_loop in Python

    def test_custom_rule_violation(self):
        """Test that a custom ast-grep rule violation returns score 0."""
        mock_root = MagicMock()
        mock_root.root().find_all.return_value = [MagicMock()]

        sa_result = StructuralAnalysisResult(roots={"main.py": mock_root})
        files = [SubmissionFile("main.py", "if True: pass")]
        custom_rules = [{"kind": "if_statement"}]
        
        result = self.test_fn.execute(files, None,
                                     custom_ast_grep_rules=custom_rules,
                                     structural_analysis=sa_result,
                                     submission_language=Language.PYTHON)
        
        assert result.score == 0.0
        assert "if_statement" in result.report

    def test_no_violation_found(self):
        """Test that no violations returns full score."""
        mock_root = MagicMock()
        mock_root.root().find_all.return_value = []

        sa_result = StructuralAnalysisResult(roots={"main.py": mock_root})
        files = [SubmissionFile("main.py", "x = 1")]
        
        result = self.test_fn.execute(files, None,
                                     forbidden_keywords=["for_loop"],
                                     structural_analysis=sa_result,
                                     submission_language=Language.PYTHON)
        
        assert result.score == 100.0
