from abc import ABC, abstractmethod
from core.config_processing.test_config import TestConfig
from core.grading.subject_grader import SubjectGrader

class BaseGrader(ABC):
    """Abstract base class for grading"""
    def __init__(self, test_file,test_config):
        self.test_file = test_file
        self.test_amount = 0  # Total number of tests in the test file
        self.test_config = test_config  # TestConfig instance containing the configuration for the test file
        self.passed_tests = []  # List of passed tests
        self.failed_tests = []  # List of failed tests
        self.quantitative_results = {}  # Dictionary to store quantitative results from tests

    @abstractmethod
    def get_test_results(self):
        pass

    def generate_score(self):
        """Generate the score based on the test results and the test configuration."""
        sub_configs = self.test_config.sub_configs  # Get the sub-configurations from the test configuration
        if sub_configs:  # If there are sub-configurations, grade each subject separately
            score = self.grade_with_sub_configs(sub_configs)
        else:  # If there are no sub-configurations, grade the entire test file
            score = self.grade()
        print(f"{self.test_config.ctype.upper()} score: {(score / 100) * self.test_config.weight}")
        print(f"\t{self.test_config.ctype.upper()} weight: {self.test_config.weight}")
        return (score / 100) * self.test_config.weight  # Return the final score as a percentage of the total weight

    def grade_with_sub_configs(self, sub_configs):
        """Grade the test file based on the sub-configurations."""
        score = 0
        for sub_config in sub_configs:
            grader = SubjectGrader.create(self.get_all_tests(), sub_config,
                                          self.test_config.ctype)  # Create a SubjectGrader instance for each sub-configuration
            score += grader.score  # Add the score of each subject to the total score
        return score
    def grade(self):
        return (len(self.passed_tests) / self.get_test_amount()) * 100 if self.test_config.weight > 0 else 0

    def get_test_amount(self):
        return len(self.passed_tests) + len (self.failed_tests)

    def get_all_tests(self):
        return self.passed_tests, self.failed_tests,self.quantitative_results

    def get_results(self):
        """Get the results of the grading process."""
        return {
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "test_amount": self.test_amount,
            "score": self.generate_score()
        }
    @classmethod
    def create(cls, test_file: str, test_config: TestConfig):
        """Create a Grader instance from a test file and a TestConfig instance."""
        grader = cls(test_file, test_config)
        grader.get_test_results()
        grader.test_amount = grader.get_test_amount()
        return grader
