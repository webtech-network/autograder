from autograder.core.test_engine.engine_port import EnginePort


class JestAdapter(EnginePort):
    """
    JestAdapter is the adapter for the Jest test framework.
    It implements the EnginePort interface to run tests and normalize output.
    """

    def run_tests(self):
        """
        Run the tests using Jest.
        This method should implement the logic to execute Jest tests.
        """
        # Placeholder for running Jest tests
        print("Running Jest tests...")

    def normalize_output(self):
        """
        Normalize the output from Jest tests.
        This method should implement the logic to format the test results.
        """
        # Placeholder for normalizing Jest test output
        print("Normalizing Jest test output...")