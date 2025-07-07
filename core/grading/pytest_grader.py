
import pytest
from utils.collector import TestCollector
from core.grading.base_grader import BaseGrader

class PytestGrader(BaseGrader):
    def get_test_results(self):
        """Run pytest on the test file and collect the results."""
        collector = TestCollector()
        result = pytest.main([f"tests/{self.test_file}"], plugins=[collector])  # "-p", "no:terminal"
        passed_tests = collector.passed
        failed_tests = collector.failed
        quantitative_tests = collector.quantitative_results
        self.set_cleaned_tests(passed_tests, failed_tests, quantitative_tests)

    def set_cleaned_tests(self, passed_tests, failed_tests, quantitative_tests):
        """Clean the test results by removing the test file path and formatting the test names."""
        self.passed_tests = [test.replace(self.test_file + "::", "") for test in passed_tests]
        self.failed_tests = [test.replace(self.test_file + "::", "") for test in failed_tests]
        self.quantitative_results = {test.replace(self.test_file + "::", ""): count for test, count in
                                     quantitative_tests.items()}
    # Clean the test results

