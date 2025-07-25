from tkinter.font import names
from utils.path import Path
from utils.config_loader import *
import json
import pytest
from utils.collector import TestCollector


class Grader:
    """Grades test files based on pytest results and predefined configurations."""

    def __init__(self, test_file: str, test_config):
        """Initializes a Grader instance.

        Args:
            test_file: Path to the test file.
            test_config: TestConfig instance containing the configuration for the test file.
        """
        self.test_file = test_file
        self.test_amount = 0
        self.test_config = test_config
        self.passed_tests = []
        self.failed_tests = []

    def get_test_results(self):
        """Runs pytest on the test file and collects the results.

        Returns:
            Tuple[List[str], List[str]]: Lists of passed and failed tests.
        """
        collector = TestCollector()
        result = pytest.main([self.test_file, "-p", "no:terminal"], plugins=[collector])
        passed_tests = collector.passed
        failed_tests = collector.failed
        return passed_tests, failed_tests

    def generate_score(self):
        """Generates the score based on test results and configuration.

        Returns:
            float: Final score as a percentage of the total weight.
        """
        sub_configs = self.test_config.sub_configs
        if sub_configs:
            score = self.grade_with_sub_configs(sub_configs)
        else:
            score = self.grade()
        return (score / 100) * self.test_config.weight

    def grade_with_sub_configs(self, sub_configs):
        """Grades the test file based on sub-configurations.

        Args:
            sub_configs: List of sub-configuration objects.

        Returns:
            float: Total score for all sub-configurations.
        """
        score = 0
        for sub_config in sub_configs:
            grader = SubjectGrader.create(self.get_all_tests(), sub_config, self.test_config.ctype)
            score += grader.score
        return score

    def grade(self):
        """Calculates the score for the entire test file.

        Returns:
            float: Ratio of passed tests to total tests.
        """
        return len(self.passed_tests) / self.get_test_amount()

    def get_test_amount(self):
        """Gets the total number of tests.

        Returns:
            int: Total number of tests (passed + failed).
        """
        return len(self.passed_tests) + len(self.failed_tests)

    def get_all_tests(self):
        """Gets all test results.

        Returns:
            Tuple[List[str], List[str]]: Passed and failed tests.
        """
        return self.passed_tests, self.failed_tests

    @classmethod
    def create(cls, test_file: str, test_config: str):
        """Creates a Grader instance from a test file and configuration.

        Args:
            test_file: Path to the test file.
            test_config: TestConfig instance.

        Returns:
            Grader: Initialized Grader instance.
        """
        grader = Grader(test_file, test_config)
        grader.passed_tests = grader.get_test_results()[0]
        grader.failed_tests = grader.get_test_results()[1]
        grader.test_amount = grader.get_test_amount()
        return grader


class SubjectGrader:
    """Grades a specific subject within a test file."""

    def __init__(self, test_report, sub_config, ctype):
        """Initializes a SubjectGrader instance.

        Args:
            test_report: Tuple containing lists of passed and failed tests.
            sub_config: SubTestConfig instance for the subject.
            ctype: Subject type (e.g., 'html', 'css', 'js').
        """
        self.test_report = test_report
        self.sub_config = sub_config
        self.ctype = ctype
        self.score = 0

    def get_all_tests(self):
        """Gets the total number of tests for the subject.

        Returns:
            int: Total number of tests.
        """
        return len(self.test_report[0]) + len(self.test_report[1])

    def generate_sub_score(self):
        """Generates the score for the subject based on test results and configuration.

        Returns:
            None
        """
        regex = f"grading/tests/test_{self.ctype}.py::{self.sub_config.convention}"
        total_tests = sum(1 for s in self.test_report[0] + self.test_report[1] if s.startswith(regex))
        passed_tests = sum(1 for s in self.test_report[0] if s.startswith(regex))
        print(f"CHECKS FOR SUBJECT {self.sub_config.ctype} had {passed_tests} passed from {total_tests} tests")
        self.score = (passed_tests / total_tests) * self.sub_config.weight

    @classmethod
    def create(cls, test_report, sub_config, ctype):
        """Creates a SubjectGrader instance and generates its score.

        Args:
            test_report: Tuple of passed and failed tests.
            sub_config: SubTestConfig instance.
            ctype: Subject type.

        Returns:
            SubjectGrader: Initialized and scored SubjectGrader instance.
        """
        response = cls(test_report, sub_config, ctype)
        response.generate_sub_score()
        return response


if __name__ == '__main__':
    # Example usage for manual testing.
    dic = json.load(open("config.json"))
    grade = Grader.create("tests/test_base.py", TestConfig.create("base", dic))
    grade2 = Grader.create("tests/test_bonus.py", TestConfig.create("bonus", dic))
    grade3 = Grader.create("tests/test_penalty.py", TestConfig.create("penalty", dic))
    print(grade.generate_score())