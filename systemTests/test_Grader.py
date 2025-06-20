import pytest
from unittest.mock import MagicMock, patch
from grading.grader import Grader
from utils.config_loader import TestConfig

@pytest.fixture
def mock_test_config():
    """Fixture to create a mock TestConfig instance."""
    mock_config = MagicMock(spec=TestConfig)
    mock_config.sub_configs = []
    mock_config.weight = 100
    mock_config.ctype = "base"
    return mock_config

@pytest.fixture
def grader_instance(mock_test_config):
    """Fixture to create a Grader instance."""
    return Grader("mock_test_file.py", mock_test_config)

def test_grader_initialization(grader_instance, mock_test_config):
    """Test the initialization of the Grader class."""
    assert grader_instance.test_file == "mock_test_file.py"
    assert grader_instance.test_config == mock_test_config
    assert grader_instance.test_amount == 0
    assert grader_instance.passed_tests == []
    assert grader_instance.failed_tests == []
    assert grader_instance.quantitative_results == {}

@patch("grading.grader.pytest.main")
def test_get_test_results(mock_pytest_main, grader_instance):
    """Test the get_test_results method."""
    mock_collector = MagicMock()
    mock_collector.passed = ["test_passed"]
    mock_collector.failed = ["test_failed"]
    mock_collector.quantitative_results = {"test_quantitative": 5}
    mock_pytest_main.return_value = 0

    with patch("grading.grader.TestCollector", return_value=mock_collector):
        passed, failed, quantitative = grader_instance.get_test_results()

    assert passed == ["test_passed"]
    assert failed == ["test_failed"]
    assert quantitative == {"test_quantitative": 5}

def test_generate_score_with_sub_configs(grader_instance, mock_test_config):
    """Test the generate_score method when sub_configs are present."""
    mock_test_config.sub_configs = [MagicMock()]
    grader_instance.grade_with_sub_configs = MagicMock(return_value=80)

    score = grader_instance.generate_score()

    assert score == 80
    grader_instance.grade_with_sub_configs.assert_called_once_with(mock_test_config.sub_configs)

def test_generate_score_without_sub_configs(grader_instance, mock_test_config):
    """Test the generate_score method when no sub_configs are present."""
    mock_test_config.sub_configs = []
    grader_instance.grade = MagicMock(return_value=0.9)

    score = grader_instance.generate_score()

    assert score == 90
    grader_instance.grade.assert_called_once()

def test_grade(grader_instance):
    """Test the grade method."""
    grader_instance.passed_tests = ["test1", "test2"]
    grader_instance.failed_tests = ["test3"]

    score = grader_instance.grade()

    assert score == 2 / 3

def test_get_test_amount(grader_instance):
    """Test the get_test_amount method."""
    grader_instance.passed_tests = ["test1", "test2"]
    grader_instance.failed_tests = ["test3"]

    test_amount = grader_instance.get_test_amount()

    assert test_amount == 3

def test_get_all_tests(grader_instance):
    """Test the get_all_tests method."""
    grader_instance.passed_tests = ["test1"]
    grader_instance.failed_tests = ["test2"]
    grader_instance.quantitative_results = {"test3": 5}

    all_tests = grader_instance.get_all_tests()

    assert all_tests == (["test1"], ["test2"], {"test3": 5})

def test_get_results(grader_instance):
    """Test the get_results method."""
    grader_instance.passed_tests = ["test1"]
    grader_instance.failed_tests = ["test2"]
    grader_instance.test_amount = 2
    grader_instance.generate_score = MagicMock(return_value=80)

    results = grader_instance.get_results()

    assert results == {
        "passed_tests": ["test1"],
        "failed_tests": ["test2"],
        "test_amount": 2,
        "score": 80
    }

@patch("grading.grader.Grader.get_test_results")
def test_create_grader(mock_get_test_results, mock_test_config):
    """Test the create class method."""
    mock_get_test_results.return_value = (["test1"], ["test2"], {"test3": 5})

    grader = Grader.create("mock_test_file.py", mock_test_config)

    assert grader.test_file == "mock_test_file.py"
    assert grader.test_config == mock_test_config
    assert grader.passed_tests == ["test1"]
    assert grader.failed_tests == ["test2"]
    assert grader.quantitative_results == {"test3": 5}
    assert grader.test_amount == 3