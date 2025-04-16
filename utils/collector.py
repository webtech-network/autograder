import pytest

class TestCollector:
    """

    """
    def __init__(self):
        self.passed = []
        self.failed = []

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            if report.failed:
                self.failed.append(report.nodeid)
            else:
                self.passed.append(report.nodeid)
