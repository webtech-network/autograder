import unittest
from unittest.mock import MagicMock
from autograder.services.report.default_reporter import DefaultReporter
from autograder.models.dataclass.feedback_preferences import FeedbackPreferences, GeneralPreferences, DefaultReporterPreferences
from autograder.models.dataclass.focus import Focus, FocusedTest
from tests.grading import leaf, outcome_tree

class TestDefaultReporter(unittest.TestCase):
    """Unit tests for the DefaultReporter."""
    def setUp(self):
        self.reporter = DefaultReporter()
        
        self.result_tree = outcome_tree(leaf("t1", 50.0, "Test 1", report="Failure message",
                                             parameters={"param1": "val1"}, file_target=["main.py"]),
                                        leaf("t2", 100.0, "Test 2"), leaf("t3", 100.0, "Test 3"),
                                        leaf("t4", 100.0, "Test 4"), leaf("t5", 100.0, "Test 5"))
        self.test_node = self.result_tree.base.tests[0]
        self.focus = Focus(
            base=[FocusedTest(test_result=self.test_node, diff_score=10.0)],
            penalty=[],
            bonus=[]
        )

    def test_generate_report_basic(self):
        """Tests basic report generation with summary and score."""
        preferences = FeedbackPreferences(
            general=GeneralPreferences(report_title="Test Report", add_report_summary=True, show_score=True),
            default=DefaultReporterPreferences()
        )
        
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        
        self.assertIn("Test Report", report)
        self.assertIn("## GRADING SUMMARY", report)
        self.assertIn("### 🧪 Test 1", report)
        self.assertIn("> **90.00 / 100**", report)
        self.assertIn("- 📁 **File:** `main.py`", report)
        self.assertIn("1 failed", report)

    def test_show_passed_tests_toggle(self):
        """Tests that passed tests are shown or hidden based on preferences."""
        # Case 1: show_passed_tests = False, test passed
        self.focus = Focus(base=[FocusedTest(test_result=self.result_tree.base.tests[1], diff_score=0.0)],
                           penalty=[], bonus=[])
        preferences = FeedbackPreferences(
            general=GeneralPreferences(show_passed_tests=False)
        )
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        self.assertNotIn("Test 2", report)
        
        # Case 2: show_passed_tests = True, test passed
        preferences.general.show_passed_tests = True
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        self.assertIn("Test 2", report)

    def test_empty_focus_graceful(self):
        """Tests that the reporter handles empty focus/tree gracefully."""
        report = self.reporter.generate_report(None, None, None)
        self.assertIn("Evaluation Report", report)
        self.assertNotIn("GRADING SUMMARY", report)

if __name__ == "__main__":
    unittest.main()
