import pytest

class TestCollector:
    def __init__(self):
        self.passed = 0

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' and report.passed:
            self.passed += 1


