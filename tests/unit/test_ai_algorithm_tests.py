"""Tests for AI-based algorithm verification tests."""

import pytest
from pydantic import ValidationError

from autograder.models.dataclass.submission import SubmissionFile
from autograder.template_library.static_analysis import (
    AiAlgorithmConfig,
    AiGraphAlgorithmTest,
    AiSearchAlgorithmTest,
    AiSortingAlgorithmTest,
    StaticAnalysisTemplate,
)


@pytest.mark.parametrize(
    "test_name,test_cls",
    [
        ("ai_sorting_algorithm", AiSortingAlgorithmTest),
        ("ai_search_algorithm", AiSearchAlgorithmTest),
        ("ai_graph_algorithm", AiGraphAlgorithmTest),
    ],
)
def test_ai_algorithm_tests_registered_in_template(test_name, test_cls):
    template = StaticAnalysisTemplate()
    test = template.get_test(test_name)
    assert isinstance(test, test_cls)
    assert test.name == test_name


@pytest.mark.parametrize(
    "test_cls,expected_name",
    [
        (AiSortingAlgorithmTest, "ai_sorting_algorithm"),
        (AiSearchAlgorithmTest, "ai_search_algorithm"),
        (AiGraphAlgorithmTest, "ai_graph_algorithm"),
    ],
)
def test_ai_algorithm_metadata(test_cls, expected_name):
    test_fn = test_cls()
    assert test_fn.name == expected_name
    assert len(test_fn.description) > 0
    params = test_fn.parameter_description
    assert len(params) == 1
    assert params[0].name == "algorithm_name"


def test_ai_algorithm_config_requires_algorithm_name():
    with pytest.raises(ValidationError):
        AiAlgorithmConfig()


def test_ai_algorithm_config_accepts_algorithm_name():
    config = AiAlgorithmConfig(algorithm_name="Quick Sort")
    assert config.algorithm_name == "Quick Sort"


def test_build_prompt_includes_algorithm_and_files():
    test_fn = AiSortingAlgorithmTest()
    files = [SubmissionFile("sort.py", "def quicksort(arr): return arr")]
    prompt = test_fn.build_prompt(files, algorithm_name="Quick Sort")
    assert "Quick Sort" in prompt
    assert "sort.py" in prompt
    assert "Score 100" in prompt


def test_build_prompt_handles_missing_files():
    test_fn = AiSearchAlgorithmTest()
    prompt = test_fn.build_prompt(None, algorithm_name="Binary Search")
    assert "Binary Search" in prompt
    assert "No submission files were provided" in prompt
