from core.config_processing.test_config import TestConfig
from core.grading.pytest_grader import PytestGrader
from core.grading.json_result_grader import JsonResultGrader




class Grader:
    @classmethod
    def create(cls, test_file: str, test_config: TestConfig):
        if getattr(test_config, "native", True):
            return PytestGrader.create(test_file, test_config)
        else:
            return JsonResultGrader.create(test_file, test_config)







