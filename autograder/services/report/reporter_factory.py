from autograder.models.dataclass.feedback_preferences import FeedbackPreferences
from autograder.models.dataclass.result import Result
from autograder.services.report.ai_reporter import AIReporter
from autograder.services.report.default_reporter import DefaultReporter
class ReporterFactory:


    @staticmethod
    def create_reporter_for(mode: str):
        """Creates a reporter instance based on the specified mode."""
        if mode == "ai":
            return ReporterFactory.create_ai_reporter()
        else:
            return ReporterFactory.create_default_reporter()


    @classmethod
    def create_ai_reporter(cls, result: Result, feedback: FeedbackPreferences,template, quota):
        """Creates an AIReporter instance with the students results"""
        return AIReporter.create(result,feedback,template,quota)

    @classmethod
    def create_default_reporter(cls, result: Result,feedback: FeedbackPreferences,template):
        """Creates a DefaultReporter instance with the students results"""
        return DefaultReporter.create(result,feedback,template)


