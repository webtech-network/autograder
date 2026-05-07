from unittest.mock import Mock, patch

import pytest

from autograder.steps.load_template_step import TemplateLoaderStep


@patch("autograder.steps.load_template_step.TemplateLibraryService.get_instance")
def test_normalizes_comma_separated_template_names(mock_get_instance):
    mock_get_instance.return_value = Mock()
    step = TemplateLoaderStep("input_output, static_analysis,")
    assert step._template_names == ["input_output", "static_analysis"]


@patch("autograder.steps.load_template_step.TemplateLibraryService.get_instance")
def test_normalizes_template_name_list(mock_get_instance):
    mock_get_instance.return_value = Mock()
    step = TemplateLoaderStep(["input_output", " static_analysis ", ""])
    assert step._template_names == ["input_output", "static_analysis"]


@patch("autograder.steps.load_template_step.TemplateLibraryService.get_instance")
def test_rejects_empty_template_names_after_normalization(mock_get_instance):
    mock_get_instance.return_value = Mock()
    with pytest.raises(ValueError, match="at least one non-empty template identifier"):
        TemplateLoaderStep(" , , ")


@patch("autograder.steps.load_template_step.TemplateLibraryService.get_instance")
def test_custom_template_allows_missing_template_names(mock_get_instance):
    mock_get_instance.return_value = Mock()
    step = TemplateLoaderStep(None, custom_template={"inline": "template"})
    assert step._template_names == []
