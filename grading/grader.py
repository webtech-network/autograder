from tkinter.font import names
from utils.path import Path
from utils.config_loader import *
import json
import pytest
from utils.collector import TestCollector


class Grader:
    """This class is used to grade test files based on the results of pytest and the predefine configurations."""
    def __init__(self,test_file: str,test_config):
        self.test_file = test_file # Path to the test file
        self.test_amount = 0 # Total number of tests in the test file
        self.test_config = test_config # TestConfig instance containing the configuration for the test file
        self.passed_tests = [] # List of passed tests
        self.failed_tests = [] # List of failed tests

    def get_test_results(self):
        """Run pytest on the test file and collect the results."""
        collector = TestCollector()
        result = pytest.main([self.test_file,"-p", "no:terminal"], plugins=[collector]) #"-p", "no:terminal"
        passed_tests = collector.passed
        failed_tests = collector.failed
        return passed_tests, failed_tests # return a tuple of lists containing passed and failed tests

    def generate_score(self):
        """Generate the score based on the test results and the test configuration."""
        sub_configs = self.test_config.sub_configs # Get the sub-configurations from the test configuration
        if sub_configs: # If there are sub-configurations, grade each subject separately
            score = self.grade_with_sub_configs(sub_configs)
        else: # If there are no sub-configurations, grade the entire test file
            score = self.grade()

        return (score/100) * self.test_config.weight # Return the final score as a percentage of the total weight

    def grade_with_sub_configs(self,sub_configs):
        """Grade the test file based on the sub-configurations."""
        score = 0
        for sub_config in sub_configs:
            grader = SubjectGrader.create(self.get_all_tests(), sub_config, self.test_config.ctype) # Create a SubjectGrader instance for each sub-configuration
            score += grader.score # Add the score of each subject to the total score
        return score

    def grade(self):
        return len(self.passed_tests) / self.get_test_amount()

    def get_test_amount(self):
        return len(self.passed_tests) + len (self.failed_tests)

    def get_all_tests(self):
        return self.passed_tests, self.failed_tests

    @classmethod
    def create(cls,test_file: str,test_config: str):
        """Create a Grader instance from a test file and a TestConfig instance."""
        grader = Grader(test_file,test_config)
        results = grader.get_test_results() # Get the test results by running pytest on the test file
        grader.passed_tests = results[0] # Set the passed tests
        grader.failed_tests = results[1]
        grader.test_amount = grader.get_test_amount()
        return grader

class SubjectGrader:
    """This class is used to grade a specific subject within a test file based on the results of pytest and the predefine configurations."""
    def __init__(self,test_report, sub_config,ctype):
        self.test_report = test_report # Tuple containing passed and failed tests
        self.sub_config = sub_config # SubTestConfig instance containing the configuration for the subject
        self.ctype = ctype # Subject type (e.g., 'html, 'css', 'js')
        self.score = 0 # Score for the subject, initialized to 0
        self.filtered = False
    def get_all_tests(self):
        return len(self.test_report[0]) + len(self.test_report[1])
    def generate_sub_score(self):
        """Generate the score for the subject based on the test results and the sub-configuration."""
        if not self.filtered:
            regex = f"tests/test_{self.ctype}.py::{self.sub_config.convention}" # Regex to match the subject tests
            total_tests = sum(1 for s in self.test_report[0]+self.test_report[1] if s.startswith(regex)) # Count the total number of tests for the subject
            passed_tests = sum(1 for s in self.test_report[0] if s.startswith(regex)) # Count the number of passed tests for the subject
        else:
            total_tests = self.get_all_tests()
            passed_tests = len(self.test_report[0])

        self.score = (passed_tests / total_tests) * self.sub_config.weight
        # Return the score as a percentage of the sub-configuration weight

    def filter_tests(self):
        """Filter the test results based on the include list."""
        passed_tests, failed_tests = self.test_report

        # Using a set for the 'include' list provides faster lookups
        if self.sub_config.include:
            # Filter both lists to keep only the tests present in the include_set
            filtered_passed = [test for test in passed_tests if test.split('::')[-1] in self.sub_config.include]
            filtered_failed = [test for test in failed_tests if test.split('::')[-1] in self.sub_config.include]
            # If the include list is empty, we keep all tests
            self.test_report = (filtered_passed, filtered_failed) # Update the test report with the filtered results
            self.filtered = True
        elif self.sub_config.exclude:
            # Filter both lists to keep only the tests not present in the include_set
            filtered_passed = [test for test in passed_tests if test.split('::')[-1] not in self.sub_config.exclude]
            filtered_failed = [test for test in failed_tests if test.split('::')[-1] not in self.sub_config.exclude]
            self.test_report = (filtered_passed, filtered_failed)



    @classmethod
    def create(cls,test_report, sub_config : SubTestConfig,ctype):
        """Create a SubjectGrader instance from a test report, a SubTestConfig instance, and a subject type.
        This method initializes the SubjectGrader, filters the tests based on the sub_config, and generates the sub score."""
        response = cls(test_report, sub_config, ctype)
        response.filter_tests()
        response.generate_sub_score()
        return response




class QuantitativeGrader:




