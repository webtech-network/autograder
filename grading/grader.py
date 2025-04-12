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
    def get_all_tests(self):
        return zip(self.passed_tests, self.failed_tests)

    @classmethod
    def create(cls,test_file: str):
        grader = Grader(test_file)
        grader.passed_tests = grader.get_test_results()[0]
        grader.failed_tests = grader.get_test_results()[1]
        grader.test_amount = grader.get_test_amount()
        return grader



if __name__ == '__main__':
    grade = Grader.create("tests/test_base.py")
    grade2 = Grader.create("tests/test_bonus.py")
    grade3 = Grader.create("tests/test_penalty.py")
    with open("log.txt","w") as log:
        for test in grade.failed_tests:
            log.write(test+"\n")
        log.write('\n')
        for test in grade2.failed_tests:
            log.write(test+"\n")
        log.write('\n')
        for test in grade3.failed_tests:
            log.write(test+"\n")







