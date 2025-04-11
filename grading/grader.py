import pytest
from utils.collector import TestCollector
from utils.path import Path

import pytest
from utils.collector import TestCollector

def get_test_results(test_file: str):
    collector = TestCollector()
    result = pytest.main([test_file,"-p","no:terminal"],plugins=[collector])
    passed_tests =  collector.passed
    failed_tests = collector.failed
    return passed_tests, failed_tests

def get_score(passed_tests,total_tests:int):
    return (len(passed_tests)/total_tests)*100









