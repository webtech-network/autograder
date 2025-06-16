import json




class Config: # This class is used to load and manage all tests configurations.
    def __init__(self):
        self.config = {}
        self.base_config = None # Configuration for tests in base_tests
        self.bonus_config = None # Configuration for tests in bonus_tests
        self.penalty_config = None # Configuration for tests in penalty_tests

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
        """Load the base configuration for tests in base_tests creating a TestConfig instance for base file config."""
        self.base_config = TestConfig.create("base", self.config)

    def load_bonus_config(self):
        """Load the bonus configuration for tests in bonus_tests creating a TestConfig instance for bonus file config."""
        self.bonus_config = TestConfig.create("bonus", self.config)

    def load_penalty_config(self):
        """Load the penalty configuration for tests in penalty_tests creating a TestConfig instance for penalty file config."""
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


class TestConfig:
    """This class is used to load and manage test configurations for different types of test files."""
    def __init__(self, ctype):
        self.ctype = ctype # ctype can be 'base', 'bonus', or 'penalty'
        self.weight = 0 # Weight of the test configuration
        self.sub_configs = [] # List of SubTestConfig instances for each subject in the test configuration

    def load(self, config: dict):
        """Load the configuration for the test type from the provided dictionary."""
        try:
            section = config[self.ctype]
            self.weight = section['weight']
            if self.load_subjects(section.get('subjects')) is True:
                self.balance_weights(self.sub_configs)
        except KeyError as e:
            raise Exception(f"Missing expected key in config for '{self.ctype}': {e}")

    def load_subjects(self, subjects: dict):
        """Load subjects and their configurations from the provided dictionary."""
        if subjects is None or subjects == {}:
            return False
        for subj, val in subjects.items():
            sub_config = SubTestConfig.create(subj, val)
            self.sub_configs.append(sub_config)
        return True

    def create_weights_dict(self,configs):
        weights = {}
        for sub_config in configs:
            weights[sub_config.ctype] = sub_config.get_weight()
        return weights

    def balance_weights_dict(self,weights_dict):
        """Balance the weights of the sub-configurations based on their individual weights."""
        total = sum(weights_dict.values())
        if total == 0:
            return {k: 0 for k in weights_dict}
        return {k: round(v * 100 / total, 2) for k, v in weights_dict.items()}

    def balance_weights(self,configs):
        """Balance the weights of the sub-configurations based on their individual weights."""
        weights = self.balance_weights_dict(self.create_weights_dict(configs))
        for sub_config in self.sub_configs:
            sub_config.weight = weights[sub_config.ctype]

    def __str__(self):
        display = f"Config ctype: {self.ctype}\n"
        display += f"Weight: {self.weight}\n"
        for sub_config in self.sub_configs:
            display += f"{sub_config}\n"
        return display

    @classmethod
    def create(cls, ctype, config_dict: dict):
        """Create a TestConfig instance from a configuration type and dictionary."""
        response = cls(ctype)
        response.load(config_dict)
        return response


class SubTestConfig(TestConfig):
    """This class is used to load and manage configurations for individual subjects in a test configuration."""
    def __init__(self, ctype):
        super().__init__(ctype)
        self.convention = ""
        self.include = []
        self.exclude = []
        self.quantitative_tests = []
        self.quantitative_tests_weight = 0

    def load(self, config: dict):
        """Load the configuration for the subject type from the provided dictionary."""
        try:
            self.weight = config['weight']
            self.convention = config['test_path']
            if config.get('include') is not None:
                self.include = config['include']
            elif config.get('exclude') is not None:
                self.exclude = config['exclude']
            if config.get('quantitative') is not None:
                print(config.get('quantitative'))
                self.load_quantitative_tests(config.get('quantitative'))
                self.balance_weights()

        except KeyError as e:
            raise Exception(f"Missing key in subtest config for '{self.ctype}': {e}")
    def load_quantitative_tests(self, section:dict):
        if section:
            if section.get('weight') is not None:
                self.quantitative_tests_weight = section['weight']
                if section.get('tests') is not None:
                    section = section['tests']
                    for test in section:
                        print("TEST NAME -> ",test)
                        if section[test].get('checks') is not None:
                            checks = section[test]['checks']
                        if section[test].get('weight') is not None:
                            weight = section[test]['weight']
                        quantitative_test = QuantitativeConfig.create(test,checks,weight)
                        self.quantitative_tests.append(quantitative_test)

    def balance_weights(self):
        """
        Balances the weights of QConfig objects proportionally to a new total weight.

        This function modifies the 'weight' attribute of the objects in the list in-place.

        Args:
            q_configs (list[QConfig]): A list of quantitative test configuration objects.
                                         Each object must have a 'weight' attribute.
            total_weight (int or float): The target total weight that the sum of all
                                         individual weights should equal.
        """
        # Calculate the current sum of all weights from the configuration objects.
        current_sum = sum(config.weight for config in self.quantitative_tests)

        # Requirement 1: If weights are already balanced or the sum is 0, do nothing.
        if current_sum == self.quantitative_tests_weight or current_sum == 0:
            return

        # Requirement 2: If weights are unbalanced, balance them proportionally.
        # Calculate the factor by which each weight needs to be scaled.
        scaling_factor = self.quantitative_tests_weight / current_sum

        # Apply the scaling factor to each configuration object's weight.
        for config in self.quantitative_tests:
            config.weight = round(config.weight * scaling_factor, 2)

        # Optional: Due to rounding, there might be a tiny difference.
        # This step ensures the sum is exactly the total_weight by adjusting the last element.
        new_sum = sum(config.weight for config in self.quantitative_tests)
        if new_sum != self.quantitative_tests_weight and self.quantitative_tests:
            self.quantitative_tests[-1].weight = round(self.quantitative_tests[-1].weight + (self.quantitative_tests_weight - new_sum), 2)
    def get_weight(self):
        """Get the weight of the sub-test configuration."""
        return self.weight

    def __str__(self):
        display = f"\tConfig ctype: {self.ctype}\n"
        display += f"\tWeight: {self.weight}\n"
        display += f"\tConvention: {self.convention}\n"
        display += f"\tInclude: {', '.join(self.include) if self.include else 'None'}\n"
        display += f"\tExclude: {', '.join(self.exclude) if self.exclude else 'None'}\n"
        if self.quantitative_tests:
            display += f"\tQuantitative tests: \n"
            display += f"\tQuantitative tests weight: {self.quantitative_tests_weight}\n"
            for qtest in self.quantitative_tests:
                display += f"{qtest}\n"
        return display
class QuantitativeConfig:
    def __init__(self,test_name,checks,weight):
        self.ctype = test_name
        self.checks = checks
        self.weight = weight
    @classmethod
    def create(cls, test_name, checks, weight):
        if checks < 0 or weight < 0 or weight > 100:
            raise Exception(f"Invalid weight: {weight}")
        response = cls(test_name, checks, weight)
        return response
    def __str__(self):
        display = f"\t\t{self.ctype}\n"
        display += f"\t\tChecks: {self.checks}\n"
        display += f"\t\tWeight: {self.weight}\n"
        return display





