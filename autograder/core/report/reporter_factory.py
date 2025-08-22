from autograder.core.report.ai_reporter import AIReporter
from autograder.core.report.default_reporter import DefaultReporter
class Reporter:
    @classmethod
    def create_ai_reporter(cls, result,openai_key,quota):
        """Creates an AIReporter instance with the students results"""
        return AIReporter.create(result,quota,openai_key)

    @classmethod
    def create_default_reporter(cls, result):
        """Creates a DefaultReporter instance with the students results"""
        return DefaultReporter.create(result)


