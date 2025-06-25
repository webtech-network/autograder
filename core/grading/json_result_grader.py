from core.grading.base_grader import BaseGrader
from core.result_processor import ResultProcessor



class JsonResultGrader(BaseGrader):
    def get_test_results(self):
        """Get the tests results from a json results file"""
        results_dict = ResultProcessor.load_results(
            f"tests/results/{self.test_file.split(".")[0]}_results.json")  # Load the test results from the specified file
        passed_tests = [test['test'] for test in results_dict[0]]
        failed_tests = [test['test'] for test in results_dict[1]]
        quantitative_tests = []
        self.passed_tests = passed_tests  # Set the passed tests
        self.failed_tests = failed_tests
        if len(results_dict) > 2:  # If there are quantitative results, set them
            quantitative_tests = {test['test']: test['count'] for test in results_dict[2]}
            self.quantitative_results = quantitative_tests

