import unittest
from unittest.mock import MagicMock
from autograder.services.report.default_reporter import DefaultReporter
from autograder.models.dataclass.feedback_preferences import FeedbackPreferences, GeneralPreferences, DefaultReporterPreferences
from autograder.models.dataclass.focus import Focus, FocusedTest
from autograder.models.result_tree import TestResultNode, ResultTree, RootResultNode

class TestDefaultReporter(unittest.TestCase):
    """Unit tests for the DefaultReporter."""
    def setUp(self):
        self.reporter = DefaultReporter()
        
        # Mock a TestResultNode
        self.test_node = MagicMock(spec=TestResultNode)
        self.test_node.name = "Test 1"
        self.test_node.score = 50.0
        self.test_node.report = "Failure message"
        self.test_node.parameters = {"param1": "val1"}
        self.test_node.test_node = MagicMock()
        self.test_node.test_node.file_target = ["main.py"]
        
        # Mock Focus
        self.focus = Focus(
            base=[FocusedTest(test_result=self.test_node, diff_score=10.0)],
            penalty=[],
            bonus=[]
        )
        
        # Mock ResultTree
        self.root = MagicMock(spec=RootResultNode)
        self.root.score = 90.0
        self.result_tree = MagicMock(spec=ResultTree)
        self.result_tree.root = self.root
        self.result_tree.template_name = "test_template"
        self.result_tree.get_all_test_results.return_value = [self.test_node]
        self.result_tree.get_passed_tests.return_value = []
        self.result_tree.get_failed_tests.return_value = [self.test_node]

    def test_generate_report_basic(self):
        """Tests basic report generation with summary and score."""
        preferences = FeedbackPreferences(
            general=GeneralPreferences(report_title="Test Report", add_report_summary=True, show_score=True),
            default=DefaultReporterPreferences()
        )
        
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        
        self.assertIn("Test Report", report)
        self.assertIn("## 📊 RESUMO", report)
        self.assertIn("### 🧪 Test 1", report)
        self.assertIn("> **90.00 / 100**", report)

    def test_show_passed_tests_toggle(self):
        """Tests that passed tests are shown or hidden based on preferences."""
        # Case 1: show_passed_tests = False, test passed
        self.test_node.score = 100.0
        preferences = FeedbackPreferences(
            general=GeneralPreferences(show_passed_tests=False)
        )
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        self.assertNotIn("Test 1", report)
        
        # Case 2: show_passed_tests = True, test passed
        preferences.general.show_passed_tests = True
        report = self.reporter.generate_report(self.focus, self.result_tree, preferences)
        self.assertIn("Test 1", report)

    def test_empty_focus_graceful(self):
        """Tests that the reporter handles empty focus/tree gracefully."""
        report = self.reporter.generate_report(None, None, None)
        self.assertIn("Relatório de Avaliação", report)
        self.assertNotIn("📊 RESUMO", report)

if __name__ == "__main__":
    unittest.main()
