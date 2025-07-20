import pytest

class TestCollector:
    """
    TestCollector collects test results, distinguishing between regular pass/fail
    validation and quantitative validation that report a specific count.
    """
    def __init__(self):
        self.passed = [] # Stores nodeids of passed regular validation (and quantitative validation that executed successfully)
        self.failed = [] # Stores nodeids of failed regular validation
        self.quantitative_results = {} # Stores quantitative results: {nodeid: {'test_name': '...', 'actual_count': N}}

    def pytest_runtest_logreport(self, report):
        """
        Pytest hook to process test reports.
        Captures pass/fail for regular validation and specific counts for quantitative validation.
        """
        if report.when == 'call':
            # Check if this test recorded a quantitative result via user_properties
            quantitative_data = next(
                (prop[1] for prop in report.user_properties if prop[0] == 'quantitative_result'),
                None
            )

            if quantitative_data != None:
                # This is a quantitative test. Record its specific count.
                self.quantitative_results[report.nodeid] = quantitative_data
                # Quantitative validation should generally "pass" in pytest execution
                # if they ran and reported their count. Their score is determined
                # by the reported count against expected_checks, not simple pass/fail.
                # Add to passed list for overall execution tracking
            elif not quantitative_data:
                # It's a regular pass/fail test
                if report.failed:
                    self.failed.append(report.nodeid)
                else:
                    self.passed.append(report.nodeid)