import pytest


def grade(test_file: str, total_tests: int):
    
    result = pytest.main([test_file,'--disable-warnings','--capture=no'])
    passed_tests =  len([test for test in result.result if test.passed])
    score = (passed_tests/ total_tests) * 100

    return score


oi = pytest.main(['../tests/test_html.py'])

