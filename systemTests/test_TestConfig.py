import pytest
from unittest.mock import MagicMock
from utils.config_loader import TestConfig, SubTestConfig

@pytest.fixture
def mock_config():
    """Fixture to create a mock configuration dictionary."""
    return {
        "base": {
            "weight": 50,
            "subjects": {
                "math": {
                    "weight": 30,
                    "test_path": "tests/math",
                    "include": ["algebra", "geometry"],
                    "quantitative": {
                        "weight": 20,
                        "tests": {
                            "test1": {"checks": 5, "weight": 10},
                            "test2": {"checks": 3, "weight": 10}
                        }
                    }
                }
            }
        }
    }

@pytest.fixture
def test_config_instance():
    """Fixture to create a TestConfig instance."""
    return TestConfig("base")

def test_test_config_initialization(test_config_instance):
    """Test the initialization of the TestConfig class."""
    assert test_config_instance.ctype == "base"
    assert test_config_instance.weight == 0
    assert test_config_instance.sub_configs == []

def test_load_valid_config(test_config_instance, mock_config):
    """Test loading a valid configuration."""
    test_config_instance.load(mock_config)
    assert test_config_instance.weight == 50
    assert len(test_config_instance.sub_configs) == 1
    assert test_config_instance.sub_configs[0].ctype == "math"
    assert test_config_instance.sub_configs[0].weight == 30

def test_load_missing_key(test_config_instance):
    """Test loading a configuration with a missing key."""
    invalid_config = {"base": {"subjects": {}}}
    with pytest.raises(Exception, match="Missing expected key in config for 'base': 'weight'"):
        test_config_instance.load(invalid_config)

def test_load_subjects_with_valid_data(test_config_instance, mock_config):
    """Test loading subjects with valid data."""
    subjects = mock_config["base"]["subjects"]
    result = test_config_instance.load_subjects(subjects)
    assert result is True
    assert len(test_config_instance.sub_configs) == 1
    assert test_config_instance.sub_configs[0].ctype == "math"

def test_load_subjects_with_empty_data(test_config_instance):
    """Test loading subjects with empty data."""
    result = test_config_instance.load_subjects({})
    assert result is False
    assert len(test_config_instance.sub_configs) == 0

def test_create_weights_dict(test_config_instance, mock_config):
    """Test creating a weights dictionary."""
    test_config_instance.load(mock_config)
    weights = test_config_instance.create_weights_dict(test_config_instance.sub_configs)
    assert weights == {"math": 30}

def test_balance_weights_dict(test_config_instance):
    """Test balancing weights in a dictionary."""
    weights = {"math": 30, "science": 70}
    balanced_weights = test_config_instance.balance_weights_dict(weights)
    assert balanced_weights == {"math": 30.0, "science": 70.0}

def test_balance_weights(test_config_instance, mock_config):
    """Test balancing weights of sub-configurations."""
    test_config_instance.load(mock_config)
    test_config_instance.balance_weights(test_config_instance.sub_configs)
    assert test_config_instance.sub_configs[0].weight == 100.0

def test_create_valid_config(mock_config):
    """Test creating a TestConfig instance with valid data."""
    test_config = TestConfig.create("base", mock_config)
    assert test_config.ctype == "base"
    assert test_config.weight == 50
    assert len(test_config.sub_configs) == 1

def test_create_invalid_config():
    """Test creating a TestConfig instance with invalid data."""
    invalid_config = {}
    with pytest.raises(Exception, match="Missing expected key in config for 'base': 'base'"):
        TestConfig.create("base", invalid_config)

def test_str_representation(test_config_instance, mock_config):
    """Test the string representation of the TestConfig class."""
    test_config_instance.load(mock_config)
    result = str(test_config_instance)
    assert "Config ctype: base" in result
    assert "Weight: 50" in result
    assert "math" in result