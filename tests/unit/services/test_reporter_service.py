import unittest
from unittest.mock import MagicMock, patch
from autograder.services.report.reporter_service import ReporterService
from autograder.services.report.ai_reporter import AiReporter
from autograder.services.report.default_reporter import DefaultReporter
from autograder.models.dataclass.step_result import StepName, StepStatus

class TestReporterService(unittest.TestCase):
    def test_init_ai_mode(self):
        service = ReporterService(feedback_mode="ai")
        self.assertIsInstance(service._reporter, AiReporter)

    def test_init_default_mode(self):
        service = ReporterService(feedback_mode="default")
        self.assertIsInstance(service._reporter, DefaultReporter)

    def test_generate_feedback_delegation(self):
        # Mocking the reporter to verify delegation
        service = ReporterService(feedback_mode="ai")
        mock_reporter = MagicMock()
        service._reporter = mock_reporter
        
        grading_result = MagicMock()
        feedback_config = {
            "general": {"report_title": "Custom Title"},
            "ai": {"feedback_tone": "friendly"},
            "default": {}
        }
        
        mock_reporter.generate_report.return_value = "Mocked Report"
        
        result_tree = MagicMock()
        result = service.generate_feedback(grading_result, result_tree, feedback_config)
        
        # Verify delegation
        mock_reporter.generate_report.assert_called_once()
        args, kwargs = mock_reporter.generate_report.call_args
        self.assertEqual(kwargs['focus'], grading_result)
        self.assertEqual(kwargs['result_tree'], result_tree)
        
        # Verify preferences parsing
        preferences = kwargs['preferences']
        self.assertEqual(preferences.general.report_title, "Custom Title")
        self.assertEqual(preferences.ai.feedback_tone, "friendly")
        
        # Verify result content
        self.assertEqual(result, "Mocked Report")

if __name__ == "__main__":
    unittest.main()
