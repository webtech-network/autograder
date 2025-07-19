from core.report.ai_reporter import AIReporter
from core.report.default_reporter import DefaultReporter
class Reporter:
    @classmethod
    def create_ai_reporter(cls, result,token,quota, openai_key=None):
        """Creates an AIReporter instance with the students results"""
        return AIReporter.create(result,token,quota,openai_key)

    @classmethod
    def create_default_reporter(cls, result,token):
        """Creates a DefaultReporter instance with the students results"""
        return DefaultReporter.create(result, token)


