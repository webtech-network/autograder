from autograder.services.report.default_reporter import DefaultReporter
from autograder.services.report.ai_reporter import AiReporter
from autograder.models.dataclass.feedback_preferences import (
    FeedbackPreferences, GeneralPreferences, AiReporterPreferences, DefaultReporterPreferences
)


class ReporterService:
    """Service that manages feedback generation using different reporter types."""

    def __init__(self, feedback_mode: str):
        if feedback_mode == "ai":
            self._reporter = AiReporter()
        else:
            self._reporter = DefaultReporter()

    @property
    def reporter(self):
        """Returns the active reporter instance."""
        return self._reporter

    def generate_feedback(self, grading_result, result_tree, feedback_config: dict, locale: str = "en"):
        """
        Parses config into FeedbackPreferences and delegates report generation to the active reporter.
        """
        # Simple manual parsing of the nested config dict into FeedbackPreferences
        general_cfg = feedback_config.get("general", {})
        ai_cfg = feedback_config.get("ai", {})
        default_cfg = feedback_config.get("default", {})

        preferences = FeedbackPreferences(
            general=GeneralPreferences(**general_cfg),
            ai=AiReporterPreferences(**ai_cfg),
            default=DefaultReporterPreferences(**default_cfg),
            locale=locale
        )

        report_content = self._reporter.generate_report(
            focus=grading_result,
            result_tree=result_tree,
            preferences=preferences
        )

        return report_content

