"""
Handles the adapter for the test language selected.
"""
from time import sleep


class TestEngine:
    """
    TestEngine is the factory class for the test engine adapters.
    It now runs tests and normalizes the output in a single async operation,
    ensuring proper setup and teardown.
    """
    fatal_error = False

    @staticmethod
    async def run(test_framework):
        """
        Creates an adapter, runs setup, executes tests, normalizes the output,
        and guarantees teardown is always performed.
        """
        runner = None  # Initialize runner to None

        # --- MODIFICATION START ---
        # The core logic is now wrapped in a try...finally block to ensure
        # that the teardown method is always called for cleanup.
        try:
            # 1. Instantiate the correct test runner
            if test_framework == "pytest":
                from autograder.core.test_engine.adapters.pytest_adapter import PytestAdapter
                runner = PytestAdapter()
            elif test_framework == "jest":
                from autograder.core.test_engine.adapters.jest_adapter import JestAdapter
                runner = JestAdapter()
            else:
                raise ValueError(f"Unsupported test framework: {test_framework}")

            # 2. Run setup commands and check for fatal errors
            if runner.setup() == 1:
                TestEngine.fatal_error = True
                return  # Exit early; the 'finally' block will still run

            # 3. Await the test runs to ensure raw reports are created first
            report_files = await runner.run_tests()
            # 4. Normalize the output synchronously after tests are complete
            runner.normalize_output(report_files)
        finally:
            # 5. 🧹 Always run teardown to terminate background processes (like servers)
            # This block executes even if an error occurs in the 'try' block.
            if runner:
                runner.teardown()
        # --- MODIFICATION END ---