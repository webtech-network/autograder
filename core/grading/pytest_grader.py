
import pytest
from utils.collector import TestCollector
from core.grading.base_grader import BaseGrader

class PytestGrader(BaseGrader):
    def get_test_results(self):
        def get_pytest_results(self):
            """Run pytest on the test file and collect the results."""
            collector = TestCollector()
            result = pytest.main([self.test_file, "-p", "no:terminal"], plugins=[collector])  # "-p", "no:terminal"
            passed_tests = collector.passed
            failed_tests = collector.failed
            quantitative_tests = collector.quantitative_results
            self.set_cleaned_tests(passed_tests, failed_tests, quantitative_tests)  # Clean the test results







