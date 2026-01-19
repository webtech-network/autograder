from autograder.services.report.default_reporter import DefaultReporter
from autograder.services.report.ai_reporter import AiReporter

class ReporterService:
    def __init__(self, feedback_mode: str):
        if feedback_mode == "ai":
            self._reporter = DefaultReporter()
        else:
            self._reporter = AiReporter()

