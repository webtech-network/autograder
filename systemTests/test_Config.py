import pytest
import json
from utils.config_loader import Config, TestConfig

@pytest.fixture
def valid_config_file(tmp_path):
    config_data = {
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
        },
        "bonus": {
            "weight": 30,
            "subjects": {}
        },
        "penalty": {
            "weight": 20,
            "subjects": {}
        }
    }
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    return str(config_file)

@pytest.fixture
def invalid_config_file(tmp_path):
    config_file = tmp_path / "invalid_config.json"
    with open(config_file, "w") as f:
        f.write("{invalid_json}")
    return str(config_file)

@pytest.fixture
def config_instance(valid_config_file):
    return Config.create_config(valid_config_file)

def test_parse_config_valid_file(valid_config_file):
    config = Config()
    config.parse_config(valid_config_file)
    assert "base" in config.config
    assert "bonus" in config.config
    assert "penalty" in config.config

def test_parse_config_file_not_found():
    config = Config()
    with pytest.raises(Exception, match="Config file 'nonexistent.json' not found."):
        config.parse_config("nonexistent.json")

def test_parse_config_invalid_json(invalid_config_file):
    config = Config()
    with pytest.raises(Exception, match="Error parsing JSON from '.*': .*"):
        config.parse_config(invalid_config_file)

def test_load_base_config(config_instance):
    assert config_instance.base_config is not None
    assert config_instance.base_config.ctype == "base"
    assert config_instance.base_config.weight == 50

def test_load_bonus_config(config_instance):
    assert config_instance.bonus_config is not None
    assert config_instance.bonus_config.ctype == "bonus"
    assert config_instance.bonus_config.weight == 30

def test_load_penalty_config(config_instance):
    assert config_instance.penalty_config is not None
    assert config_instance.penalty_config.ctype == "penalty"
    assert config_instance.penalty_config.weight == 20

def test_create_config_valid(valid_config_file):
    config = Config.create_config(valid_config_file)
    assert config.base_config is not None
    assert config.bonus_config is not None
    assert config.penalty_config is not None

def test_create_config_invalid(invalid_config_file):
    with pytest.raises(Exception, match="Failed to create config: .*"):
        Config.create_config(invalid_config_file)

def test_base_config_subjects(config_instance):
    base_config = config_instance.base_config
    assert len(base_config.sub_configs) == 1
    math_config = base_config.sub_configs[0]
    assert math_config.ctype == "math"
    assert math_config.weight == 30
    assert math_config.convention == "tests/math"
    assert math_config.include == ["algebra", "geometry"]

def test_base_config_quantitative_tests(config_instance):
    math_config = config_instance.base_config.sub_configs[0]
    quantitative_tests = math_config.get_quantitative_tests()
    assert "test1" in quantitative_tests
    assert "test2" in quantitative_tests
    assert quantitative_tests["test1"].checks == 5
    assert quantitative_tests["test1"].weight == 10
    assert quantitative_tests["test2"].checks == 3
    assert quantitative_tests["test2"].weight == 10