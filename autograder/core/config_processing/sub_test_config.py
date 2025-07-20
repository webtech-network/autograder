from autograder.core.config_processing.test_config import TestConfig
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
                #(config.get('quantitative'))
                self.load_quantitative_tests(config.get('quantitative'))
                self.balance_weights()

        except KeyError as e:
            raise Exception(f"Missing key in subtest config for '{self.ctype}': {e}")
    def load_quantitative_tests(self, section:dict):
        if section:
            if section.get('weight') is not None:
                self.quantitative_tests_weight = section['weight']
                if section.get('validation') is not None:
                    section = section['validation']
                    for test in section:
                        if section[test].get('checks') is not None:
                            checks = section[test]['checks']
                        if section[test].get('weight') is not None:
                            weight = section[test]['weight']
                        quantitative_test = QuantitativeConfig.create(test,checks,weight) #It is complaining because checks and weight are only defined if the sections are not empty.
                        self.quantitative_tests.append(quantitative_test)

    def get_quantitative_tests(self):
        """Get the names of the quantitative validation."""
        return {qtest.ctype:qtest for qtest in self.quantitative_tests}

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
        if current_sum == 100 or current_sum == 0:
            return

        # Requirement 2: If weights are unbalanced, balance them proportionally.
        # Calculate the factor by which each weight needs to be scaled.
        scaling_factor = 100 / current_sum

        # Apply the scaling factor to each configuration object's weight.
        for config in self.quantitative_tests:
            config.weight = round(config.weight * scaling_factor, 2)

        # Optional: Due to rounding, there might be a tiny difference.
        # This step ensures the sum is exactly the total_weight by adjusting the last element.
        new_sum = sum(config.weight for config in self.quantitative_tests)
        if new_sum != self.quantitative_tests_weight and self.quantitative_tests:
            self.quantitative_tests[-1].weight = round(self.quantitative_tests[-1].weight + (100 - new_sum), 2)
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
            display += f"\tQuantitative validation: \n"
            display += f"\tQuantitative validation weight: {self.quantitative_tests_weight}\n"
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