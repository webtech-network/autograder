from tkinter.font import names

import pytest
from utils.collector import TestCollector
from utils.path import Path

import pytest
from utils.collector import TestCollector


class Grader:
    def __init__(self,test_file: str):
        self.test_file = test_file
        self.test_amount = 0
        self.passed_tests = []
        self.failed_tests = []

    def get_test_results(self):
        collector = TestCollector()
        result = pytest.main([self.test_file, "-p", "no:terminal"], plugins=[collector])
        passed_tests = collector.passed
        failed_tests = collector.failed
        return passed_tests, failed_tests

    def get_score(self):
        return (len(self.passed_tests)/self.test_amount)*100

    def get_test_amount(self):
        return len(self.passed_tests) + len (self.failed_tests)

    @classmethod
    def create(cls,test_file: str):
        grader = Grader(test_file)
        grader.passed_tests = grader.get_test_results()[0]
        grader.failed_tests = grader.get_test_results()[1]
        grader.test_amount = grader.get_test_amount()
        return grader










