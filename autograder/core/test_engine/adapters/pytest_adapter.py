from autograder.core.test_engine.engine_port import EnginePort

class PytestAdapter(EnginePort):
    """
    PytestAdapter is the adapter for the Pytest test framework.
    It implements the EnginePort interface to run tests and normalize output.
    """

    def run_tests(self):
        """
        Run the tests using Pytest.
        This method should implement the logic to execute Pytest tests.
        """
        # Placeholder for running Pytest tests
        print("Running Pytest tests...")

    def normalize_output(self):
        """
        Normalize the output from Pytest tests.
        This method should implement the logic to format the test results.
        """
        # Placeholder for normalizing Pytest test output
        print("Normalizing Pytest test output...")