import json

class Config:
    """Loads and manages all test configurations."""

    def __init__(self):
        """Initializes a Config instance."""
        self.config = {}
        self.base_config = None  # Configuration for tests in base_tests.
        self.bonus_config = None  # Configuration for tests in bonus_tests.
        self.penalty_config = None  # Configuration for tests in penalty_tests.

    def parse_config(self, config_file: str):
        """Parses the configuration file and loads the JSON data.

        Args:
            config_file: Path to the configuration file.

        Raises:
            Exception: If the file is not found or JSON parsing fails.
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                self.config = json.load(file)
        except FileNotFoundError:
            raise Exception(f"Config file '{config_file}' not found.")
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing JSON from '{config_file}': {e}")

    def load_base_config(self):
        """Loads the base configuration for tests in base_tests.

        Creates a TestConfig instance for the base file configuration.
        """
        self.base_config = TestConfig.create("base", self.config)

    def load_bonus_config(self):
        """Loads the bonus configuration for tests in bonus_tests.

        Creates a TestConfig instance for the bonus file configuration.
        """
        self.bonus_config = TestConfig.create("bonus", self.config)

    def load_penalty_config(self):
        """Loads the penalty configuration for tests in penalty_tests.

        Creates a TestConfig instance for the penalty file configuration.
        """
        self.penalty_config = TestConfig.create("penalty", self.config)

    @classmethod
    def create_config(cls, config_file: str):
        """Creates a Config instance from a configuration file.

        Args:
            config_file: Path to the configuration file.

        Returns:
            Config: Initialized Config instance.

        Raises:
            Exception: If the configuration creation fails.
        """
        response = cls()
        try:
            response.parse_config(config_file)
            response.load_base_config()
            response.load_bonus_config()
            response.load_penalty_config()
        except Exception as e:
            raise Exception(f"Failed to create config: {e}")
        return response


class TestConfig:
    """Manages test configurations for different types of test files."""

    def __init__(self, ctype):
        """Initializes a TestConfig instance.

        Args:
            ctype: Configuration type ('base', 'bonus', or 'penalty').
        """
        self.ctype = ctype
        self.weight = 0  # Weight of the test configuration.
        self.sub_configs = []  # List of SubTestConfig instances for each subject.

    def load(self, config: dict):
        """Loads the configuration for the test type from the provided dictionary.

        Args:
            config: Dictionary containing the configuration data.

        Raises:
            Exception: If a required key is missing in the configuration.
        """
        try:
            section = config[self.ctype]
            self.weight = section['weight']
            if self.load_subjects(section['subjects'].items()):
                self.balance_weights()
        except KeyError as e:
            raise Exception(f"Missing expected key in config for '{self.ctype}': {e}")

    def load_subjects(self, subjects: dict):
        """Loads subjects and their configurations from the provided dictionary.

        Args:
            subjects: Dictionary containing subject configurations.

        Returns:
            bool: True if subjects were loaded successfully, False otherwise.
        """
        if not subjects:
            return False
        for subj, val in subjects.items():
            sub_config = SubTestConfig.create(subj, val)
            self.sub_configs.append(sub_config)
        return True

    def create_weights_dict(self):
        """Creates a dictionary of weights for sub-configurations.

        Returns:
            dict: Dictionary mapping subject types to their weights.
        """
        weights = {}
        for sub_config in self.sub_configs:
            weights[sub_config.ctype] = sub_config.get_weight()
        return weights

    def balance_weights_dict(self, weights_dict):
        """Balances the weights of the sub-configurations.

        Args:
            weights_dict: Dictionary mapping subject types to their weights.

        Returns:
            dict: Dictionary with balanced weights.
        """
        total = sum(weights_dict.values())
        if total == 0:
            return {k: 0 for k in weights_dict}
        return {k: round(v * 100 / total, 2) for k, v in weights_dict.items()}

    def balance_weights(self):
        """Balances the weights of the sub-configurations."""
        weights = self.balance_weights_dict(self.create_weights_dict())
        for sub_config in self.sub_configs:
            sub_config.weight = weights[sub_config.ctype]

    def __str__(self):
        """Returns a string representation of the TestConfig instance.

        Returns:
            str: String representation of the configuration.
        """
        display = f"Config ctype: {self.ctype}\n"
        display += f"Weight: {self.weight}\n"
        for sub_config in self.sub_configs:
            display += f"{sub_config}\n"
        return display

    @classmethod
    def create(cls, ctype, config_dict: dict):
        """Creates a TestConfig instance from a configuration type and dictionary.

        Args:
            ctype: Configuration type ('base', 'bonus', or 'penalty').
            config_dict: Dictionary containing the configuration data.

        Returns:
            TestConfig: Initialized TestConfig instance.
        """
        response = cls(ctype)
        response.load(config_dict)
        return response


class SubTestConfig(TestConfig):
    """Manages configurations for individual subjects in a test configuration."""

    def __init__(self, ctype):
        """Initializes a SubTestConfig instance.

        Args:
            ctype: Subject type.
        """
        super().__init__(ctype)
        self.convention = ""

    def load(self, config: dict):
        """Loads the configuration for the subject type from the provided dictionary.

        Args:
            config: Dictionary containing the subject configuration.

        Raises:
            Exception: If a required key is missing in the configuration.
        """
        try:
            self.weight = config['weight']
            self.convention = config['test_path']
        except KeyError as e:
            raise Exception(f"Missing key in subtest config for '{self.ctype}': {e}")

    def __str__(self):
        """Returns a string representation of the SubTestConfig instance.

        Returns:
            str: String representation of the subject configuration.
        """
        display = f"\tConfig ctype: {self.ctype}\n"
        display += f"\tWeight: {self.weight}\n"
        display += f"\tConvention: {self.convention}\n"
        return display
