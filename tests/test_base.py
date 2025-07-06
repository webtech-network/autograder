# tests/test_base.py
import pytest
from submission.calculator import Calculator

@pytest.fixture
def calc():
    return Calculator()

def test_add(calc):
    """
    pass: The add function works correctly.
    fail: The add function failed. Expected 2 + 3 = 5.
    """
    assert calc.add(2, 3) == 5

def test_subtract(calc):
    """
    pass: The subtract function works correctly.
    fail: The subtract function failed. Expected 5 - 3 = 2.
    """
    # This test will fail due to the bug in the submission
    assert calc.subtract(5, 3) == 2

def test_multiply(calc):
    """
    pass: The multiply function works correctly.
    fail: The multiply function failed. Expected 3 * 4 = 12.
    """
    assert calc.multiply(3, 4) == 12

def test_divide(calc):
    """
    pass: The divide function works correctly for valid inputs.
    fail: The divide function failed. Expected 10 / 2 = 5.
    """
    assert calc.divide(10, 2) == 5

def test_divide_by_zero(calc):
    """
    pass: The divide function correctly handles division by zero by raising an exception.
    fail: The divide function did not raise a ZeroDivisionError when dividing by zero.
    """
    # This test will fail because the submission does not handle this case
    with pytest.raises(ZeroDivisionError):
        calc.divide(10, 0)