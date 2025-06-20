import pytest
from unittest.mock import MagicMock
from utils.config_loader import SubTestConfig, QuantitativeConfig

@pytest.fixture
def mock_sub_config_data():
    """Fixture to provide mock data for SubTestConfig."""
    return {
        "weight": 50,
        "test_path": "tests/math",
        "include": ["test1", "test2"],
        "exclude": [],
        "quantitative": {
            "weight": 30,
            "tests": {
                "test_quantitative1": {"checks": 5, "weight": 10},
                "test_quantitative2": {"checks": 3, "weight": 20}
            }
        }
    }

@pytest.fixture
def sub_test_config_instance():
    """Fixture to create a SubTestConfig instance."""
    return SubTestConfig("math")

def test_sub_test_config_initialization(sub_test_config_instance):
    """Test the initialization of the SubTestConfig class."""
    assert sub_test_config_instance.ctype == "math"
    assert sub_test_config_instance.weight == 0
    assert sub_test_config_instance.convention == ""
    assert sub_test_config_instance.include == []
    assert sub_test_config_instance.exclude == []
    assert sub_test_config_instance.quantitative_tests == []
    assert sub_test_config_instance.quantitative_tests_weight == 0

def test_load_valid_config(sub_test_config_instance, mock_sub_config_data):
    """Test loading a valid configuration."""
    sub_test_config_instance.load(mock_sub_config_data)
    assert sub_test_config_instance.weight == 50
    assert sub_test_config_instance.convention == "tests/math"
    assert sub_test_config_instance.include == ["test1", "test2"]
    assert sub_test_config_instance.exclude == []
    assert len(sub_test_config_instance.quantitative_tests) == 2
    assert sub_test_config_instance.quantitative_tests_weight == 30

def test_load_missing_key(sub_test_config_instance):
    """Test loading a configuration with a missing key."""
    invalid_config = {"weight": 50}
    with pytest.raises(Exception, match="Missing key in subtest config for 'math'"):
        sub_test_config_instance.load(invalid_config)

def test_load_quantitative_tests(sub_test_config_instance, mock_sub_config_data):
    """Test loading quantitative tests."""
    quantitative_section = mock_sub_config_data["quantitative"]
    sub_test_config_instance.load_quantitative_tests(quantitative_section)
    assert len(sub_test_config_instance.quantitative_tests) == 2
    assert sub_test_config_instance.quantitative_tests_weight == 30
    assert sub_test_config_instance.quantitative_tests[0].ctype == "test_quantitative1"
    assert sub_test_config_instance.quantitative_tests[0].checks == 5
    assert sub_test_config_instance.quantitative_tests[0].weight == 10

def test_get_quantitative_tests(sub_test_config_instance, mock_sub_config_data):
    """Test retrieving quantitative tests."""
    sub_test_config_instance.load(mock_sub_config_data)
    quantitative_tests = sub_test_config_instance.get_quantitative_tests()
    assert "test_quantitative1" in quantitative_tests
    assert "test_quantitative2" in quantitative_tests
    assert quantitative_tests["test_quantitative1"].checks == 5
    assert quantitative_tests["test_quantitative1"].weight == 10

def test_balance_weights(sub_test_config_instance, mock_sub_config_data):
    """Test balancing weights of quantitative tests."""
    sub_test_config_instance.load(mock_sub_config_data)
    sub_test_config_instance.quantitative_tests[0].weight = 10
    sub_test_config_instance.quantitative_tests[1].weight = 20
    sub_test_config_instance.balance_weights()
    assert sub_test_config_instance.quantitative_tests[0].weight == 33.33
    assert sub_test_config_instance.quantitative_tests[1].weight == 66.67

def test_get_weight(sub_test_config_instance, mock_sub_config_data):
    """Test retrieving the weight of the sub-test configuration."""
    sub_test_config_instance.load(mock_sub_config_data)
    assert sub_test_config_instance.get_weight() == 50

def test_str_representation(sub_test_config_instance, mock_sub_config_data):
    """Test the string representation of the SubTestConfig class."""
    sub_test_config_instance.load(mock_sub_config_data)
    result = str(sub_test_config_instance)
    assert "Config ctype: math" in result
    assert "Weight: 50" in result
    assert "Convention: tests/math" in result
    assert "Include: test1, test2" in result
    assert "Quantitative tests weight: 30" in result
    assert "test_quantitative1" in result
    assert "test_quantitative2" in result