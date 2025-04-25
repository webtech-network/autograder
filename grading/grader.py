from tkinter.font import names
from utils.path import Path
from utils.config_loader import *
import json
import pytest
from utils.collector import TestCollector


class Grader:
    """

    """
    def __init__(self,test_file: str,test_config):
        self.test_file = test_file
        self.test_amount = 0
        self.test_config = test_config
        self.passed_tests = []
        self.failed_tests = []

    def get_test_results(self):
        collector = TestCollector()
        result = pytest.main([self.test_file, "-p", "no:terminal"], plugins=[collector])
        passed_tests = collector.passed
        failed_tests = collector.failed
        return passed_tests, failed_tests

    def generate_score(self):
        sub_configs = self.test_config.sub_configs
        if sub_configs:
            score = self.grade_with_sub_configs(sub_configs)
        else:
            score = self.grade()

        return (score/100) * self.test_config.weight

    def grade_with_sub_configs(self,sub_configs):
        score = 0
        for sub_config in sub_configs:
            grader = SubjectGrader.create(self.get_all_tests(), sub_config, self.test_config.ctype)
            score += grader.score
        return score

    def grade(self):
        return len(self.passed_tests) / self.get_test_amount()

    def get_test_amount(self):
        return len(self.passed_tests) + len (self.failed_tests)

    def get_all_tests(self):
        return self.passed_tests, self.failed_tests

    @classmethod
    def create(cls,test_file: str,test_config: str):
        grader = Grader(test_file,test_config)
        grader.passed_tests = grader.get_test_results()[0]
        grader.failed_tests = grader.get_test_results()[1]
        grader.test_amount = grader.get_test_amount()
        return grader

class SubjectGrader:
    def __init__(self, test_report, sub_config,ctype):
        self.test_report = test_report
        self.sub_config = sub_config
        self.ctype = ctype
        self.score = 0

    def get_all_tests(self):
        return len(self.test_report[0]) + len(self.test_report[1])

    def get_selected_tests(self):
        # Apply include/exclude logic
        regex_prefix = f"grading/tests/test_{self.ctype}.py::{self.sub_config.convention}"
        all_tests = [s for s in self.test_report[0] + self.test_report[1] if s.startswith(regex_prefix)]
        if self.sub_config.include:
            all_tests = [t for t in all_tests if any(t.endswith(name) for name in self.sub_config.include)]
        elif self.sub_config.exclude:
            all_tests = [t for t in all_tests if not any(t.endswith(name) for name in self.sub_config.exclude)]
        return all_tests

    def generate_sub_score(self):
        all_tests = self.get_selected_tests()
        passed_tests = [t for t in self.test_report[0] if t in all_tests]
        total_tests = len(all_tests)

        print(f"CHECKS FOR SUBJECT {self.sub_config.ctype} had {len(passed_tests)} passed from {total_tests} tests")

        self.score = (len(passed_tests) / total_tests) * self.sub_config.weight if total_tests > 0 else 0

    @classmethod
    def create(cls,test_report, sub_config,ctype):
        response = cls(test_report,sub_config,ctype)
        response.generate_sub_score()
        return response


if __name__ == '__main__':
    dic = json.load(open("config.json"))
    grade = Grader.create("tests/test_base.py",TestConfig.create("base",dic))
    grade2 = Grader.create("tests/test_bonus.py",TestConfig.create("bonus",dic))
    grade3 = Grader.create("tests/test_penalty.py",TestConfig.create("penalty",dic))
    print(grade.generate_score())








