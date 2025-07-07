# tests/test_penalty.py
import pytest
import inspect
from submission.calculator import Calculator


def test_for_missing_docstrings():
    """
    pass: A function without a docstring was found. Remember to document all your functions.
    fail: All functions are correctly documented with docstrings. Great job!
    """
    # This is a penalty test, so it "passes" if it finds a problem.
    # The logic is inverted: an `assert` failure means the student did well.
    # The subtract function in the submission is missing a docstring.

    has_missing_docstring = False
    for name, method in inspect.getmembers(Calculator, predicate=inspect.isfunction):
        if not inspect.getdoc(method):
            has_missing_docstring = True
            break

    assert has_missing_docstring, "Penalty not applied: All functions have docstrings."