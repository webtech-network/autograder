import json

class ResultProcessor:
    """Processes a test file JSON report and returns the test results."""

    @staticmethod
    def load_results(result_file_path):
        with open(result_file_path, "r") as f:
            data = json.load(f)
        # data is a list of test result dicts
        passed_tests = [test for test in data if test.get("status") == "passed"]
        failed_tests = [test for test in data if test.get("status") == "failed"]
        quantitative_results = {}  # Not present in this format
        return passed_tests, failed_tests, quantitative_results