"""Result Processor module."""

import json
import os


class ResultProcessor:
    # Define the project root here as well to ensure paths are consistent
    _PROJECT_ROOT = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

    @staticmethod
    def load_results(result_file_name: str) -> dict:
        """Loads test results from a JSON file using an absolute path."""
        # Construct the absolute path from the project root
        print("PROJECT ROOT:", ResultProcessor._PROJECT_ROOT)
        absolute_path = os.path.join(
            ResultProcessor._PROJECT_ROOT,
            "validation",
            "__tests__",
            "results",
            result_file_name,
        )

        print(f"Attempting to load results from: {absolute_path}")
        try:
            with open(absolute_path, "r") as f:
                data = json.load(f)
            # data is a list of test result dicts
            passed_tests = [test for test in data if test.get("status") == "passed"]
            failed_tests = [test for test in data if test.get("status") == "failed"]
            quantitative_results = {}  # Not present in this format
            return passed_tests, failed_tests, quantitative_results
        except FileNotFoundError:
            print(
                f"ERROR: File not found at {absolute_path}. This indicates a race condition or a file naming mismatch."
            )
            raise
        except json.JSONDecodeError:
            print(
                f"ERROR: Could not decode JSON from {absolute_path}. The file might be empty or malformed."
            )
            raise
