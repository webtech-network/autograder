# tests/test_bonus.py
import pytest
from submission.calculator import Calculator

@pytest.fixture
def calc():
    return Calculator()

def test_power_function(calc):
    """
    pass: Excellent! The bonus power function was implemented correctly.
    fail: The bonus power function was not implemented or is incorrect.
    """
    assert hasattr(calc, 'power')
    assert calc.power(2, 3) == 8