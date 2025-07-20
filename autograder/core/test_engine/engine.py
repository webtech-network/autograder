"""
Handles the adapter for the test language selected.
"""

class TestEngine:
    """
    TestEngine is the factory class for the test engine adapters.
    """
    @classmethod
    def run_tests(cls, test_framework):
        """
        Create a test engine adapter based on the test framework.

        :param test_framework: The test framework to use (e.g., 'pytest', 'unittest').
        :return: An instance of the appropriate test engine adapter.
        """
        if test_framework == "pytest":
            from autograder.core.test_engine.adapters.pytest_adapter import PytestAdapter
            runner = PytestAdapter()
        elif test_framework == "unittest":
            from autograder.core.test_engine.adapters.jest_adapter import JestAdapter
            runner = JestAdapter()
        else:
            raise ValueError(f"Unsupported test framework: {test_framework}")
        runner.run_tests()
        runner.normalize_output()




