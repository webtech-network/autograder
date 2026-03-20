import unittest
from unittest.mock import MagicMock
from autograder.services.report.reporter_service import ReporterService
from autograder.services.report.ai_reporter import AiReporter
from autograder.services.report.default_reporter import DefaultReporter

class TestReporterService(unittest.TestCase):
    """Unit tests for the ReporterService."""
    def test_init_ai_mode(self):
        """Tests that ReporterService initializes AiReporter in 'ai' mode."""
        service = ReporterService(feedback_mode="ai")
        self.assertIsInstance(service.reporter, AiReporter)

    def test_init_default_mode(self):
        """Tests that ReporterService initializes DefaultReporter in 'default' mode."""
        service = ReporterService(feedback_mode="default")
        self.assertIsInstance(service.reporter, DefaultReporter)

    def test_generate_feedback_delegation(self):
        """Tests that generate_feedback delegates the call to the active reporter."""
        # Mocking the reporter to verify delegation
        service = ReporterService(feedback_mode="ai")
        mock_reporter = MagicMock()
        # It's better to inject the mock or use self.service.reporter if we had a setter,
        # but here we'll use protected access for mocking or just use the property if it had a setter.
        # Since we only have a getter, we still need to set _reporter directly for mocking purposes.
        # However, to satisfy Pylint without disable, we can use setattr.
        setattr(service, "_reporter", mock_reporter)
        
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
        _, kwargs = mock_reporter.generate_report.call_args
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
