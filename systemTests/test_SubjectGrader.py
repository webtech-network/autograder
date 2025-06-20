import pytest
from unittest.mock import MagicMock
from grading.grader import SubjectGrader
from utils.config_loader import SubTestConfig

@pytest.fixture
def mock_sub_config():
    """Fixture to create a mock SubTestConfig instance."""
    sub_config = MagicMock(spec=SubTestConfig)
    sub_config.weight = 50
    sub_config.quantitative_tests_weight = 30
    sub_config.include = ["test1", "test2"]
    sub_config.exclude = []
    sub_config.get_quantitative_tests.return_value = {
        "test_quantitative1": MagicMock(checks=5, weight=10),
        "test_quantitative2": MagicMock(checks=3, weight=20),
    }
    return sub_config

@pytest.fixture
def mock_test_report():
    """Fixture to create a sample test report."""
    passed_tests = ["grading/tests/test_html.py::test1", "grading/tests/test_html.py::test2"]
    failed_tests = ["grading/tests/test_html.py::test3"]
    quantitative_results = {
        "grading/tests/test_html.py::test_quantitative1": 4,
        "grading/tests/test_html.py::test_quantitative2": 3,
    }
    return (passed_tests, failed_tests, quantitative_results)

@pytest.fixture
def subject_grader_instance(mock_test_report, mock_sub_config):
    """Fixture to create a SubjectGrader instance."""
    return SubjectGrader(mock_test_report, mock_sub_config, "html")

def test_subject_grader_initialization(subject_grader_instance, mock_test_report, mock_sub_config):
    """Test the initialization of the SubjectGrader class."""
    assert subject_grader_instance.test_report == mock_test_report
    assert subject_grader_instance.sub_config == mock_sub_config
    assert subject_grader_instance.ctype == "html"
    assert subject_grader_instance.score == 0
    assert subject_grader_instance.filtered is False
    assert subject_grader_instance.quantitative_report == {}

def test_generate_sub_score(subject_grader_instance):
    """Test the generate_sub_score method."""
    subject_grader_instance.get_unit_tests_score = MagicMock(return_value=40)
    subject_grader_instance.get_quantitative_score = MagicMock(return_value=20)
    subject_grader_instance.generate_sub_score()
    assert subject_grader_instance.score == 30  # (40 + 20) / 100 * 50

def test_get_unit_tests_score(subject_grader_instance, mock_test_report, mock_sub_config):
    """Test the get_unit_tests_score method."""
    mock_sub_config.quantitative_tests_weight = 20
    score = subject_grader_instance.get_unit_tests_score()
    assert score == (2 / 3) * 80  # 2 passed out of 3 total, adjusted by unit tests weight

def test_get_quantitative_score(subject_grader_instance, mock_sub_config):
    """Test the get_quantitative_score method."""
    subject_grader_instance.quantitative_report = {
        "test_quantitative1": 4,
        "test_quantitative2": 3,
    }
    score = subject_grader_instance.get_quantitative_score()
    assert score == 30  # Calculated based on quantitative test weights and results

def test_load_tests(subject_grader_instance, mock_test_report):
    """Test the load_tests method."""
    subject_grader_instance.load_tests()
    assert subject_grader_instance.test_report[0] == ["grading/tests/test_html.py::test1", "grading/tests/test2"]
    assert subject_grader_instance.test_report[1] == []
    assert subject_grader_instance.filtered is True

def test_filter_configs(subject_grader_instance, mock_sub_config):
    """Test the filter_configs method."""
    configs = mock_sub_config.get_quantitative_tests()
    filtered_configs = subject_grader_instance.filter_configs(configs)
    assert "test_quantitative1" in filtered_configs
    assert "test_quantitative2" in filtered_configs

def test_balance_active_quantitative_tests(subject_grader_instance, mock_sub_config):
    """Test the balance_active_quantitative_tests method."""
    configs = mock_sub_config.get_quantitative_tests()
    subject_grader_instance.balance_active_quantitative_tests(configs)
    total_weight = sum(config.weight for config in configs.values())
    assert total_weight == 100

def test_create(mock_test_report, mock_sub_config):
    """Test the create class method."""
    subject_grader = SubjectGrader.create(mock_test_report, mock_sub_config, "html")
    assert subject_grader.test_report == mock_test_report
    assert subject_grader.sub_config == mock_sub_config
    assert subject_grader.ctype == "html"
    assert subject_grader.score > 0