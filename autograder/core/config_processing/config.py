import json
from autograder.core.config_processing.test_config import TestConfig
class Config: # This class is used to load and manage all validation configurations.
    def __init__(self):
        self.config = {}
        self.base_config = None # Configuration for validation in base_tests
        self.bonus_config = None # Configuration for validation in bonus_tests
        self.penalty_config = None # Configuration for validation in penalty_tests

    def parse_config(self, config_file: str):
        """Parse the configuration file and load the JSON data."""
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                self.config = json.load(file)

        except FileNotFoundError:
            raise Exception(f"Config file '{config_file}' not found.")
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing JSON from '{config_file}': {e}")

    def load_base_config(self):
        """Load the base configuration for validation in base_tests creating a TestConfig instance for base file config."""
        self.base_config = TestConfig.create("base", self.config)

    def load_bonus_config(self):
        """Load the bonus configuration for validation in bonus_tests creating a TestConfig instance for bonus file config."""
        self.bonus_config = TestConfig.create("bonus", self.config)

    def load_penalty_config(self):
        """Load the penalty configuration for validation in penalty_tests creating a TestConfig instance for penalty file config."""
        self.penalty_config = TestConfig.create("penalty", self.config)

    @classmethod
    def create_config(cls, config_file: str):
        """Create a Config instance from a configuration file."""
        response = cls()
        try:
            response.parse_config(config_file)
            response.load_base_config()
            response.load_bonus_config()
            response.load_penalty_config()
        except Exception as e:
            raise Exception(f"Failed to create config: {e}")
        return response
