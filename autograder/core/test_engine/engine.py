"""
Handles the adapter for the test language selected.
"""
class TestEngine:
    """
    TestEngine is the factory class for the test engine adapters.
    It now runs tests and normalizes the output in a single async operation.
    """
    @classmethod
    async def run_tests(cls, test_framework):
        """
        Creates an adapter, runs tests, and normalizes the output,
        ensuring all steps complete before returning.
        """
        runner = None
        if test_framework == "pytest":
            from autograder.core.test_engine.adapters.pytest_adapter import PytestAdapter
            runner = PytestAdapter()
        elif test_framework == "jest":
            from autograder.core.test_engine.adapters.jest_adapter import JestAdapter
            runner = JestAdapter()
        else:
            raise ValueError(f"Unsupported test framework: {test_framework}")

        # --- KEY FIX ---
        # Await the test runs to ensure raw reports are created first.
        report_files = await runner.run_tests()

        # Now, call the synchronous normalize_output. Because the 'run_tests'
        # was properly awaited, this will only execute after the tests are done.
        # This function will create the final "..._results.json" files.
        runner.normalize_output(report_files)

        # There is no need to make normalize_output async if it only does
        # CPU-bound and fast file I/O tasks. The crucial part is that
        # the entire run_tests method in the engine completes before
        # control is returned to the facade.