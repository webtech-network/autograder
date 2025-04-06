import pytest
from utils.collector import TestCollector

def grade(test_file: str, total_tests: int):
    collector = TestCollector()
    result = pytest.main([test_file,'--disable-warnings','--capture=no'],plugins=[collector])
    passed_tests =  collector.passed
    score = (passed_tests/ total_tests) * 100
    return score



