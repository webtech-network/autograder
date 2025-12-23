import unittest
from autograder.services.report import DefaultReporter
from autograder.models.dataclass.result import Result
from autograder.models.dataclass.test_result import TestResult
from autograder.models.dataclass.feedback_preferences import FeedbackPreferences


class TestDefaultReporter(unittest.TestCase):

    def setUp(self):
        """Set up a mock Result and FeedbackPreferences object for testing."""

        # Create a variety of test results for different scenarios
        base_results = [
            TestResult("passing_base_test", 100, "Base test passed.", "html"),
            TestResult("failing_base_test", 0, "Base test failed.", "css", {"file": "style.css"})
        ]
        bonus_results = [
            TestResult("passing_bonus_test", 100, "Bonus achieved!", "javascript"),
            TestResult("failing_bonus_test", 50, "Bonus partially met.", "accessibility")
        ]
        penalty_results = [
            TestResult("passing_penalty_test", 100, "Penalty avoided.", "html_validation"),
            TestResult("failing_penalty_test", 0, "Penalty applied for malpractice.", "js_malpractice")
        ]

        self.mock_result = Result(
            final_score=75.5,
            author="Jane Doe",
            submission_file={"index.html": ""},
            base_results=base_results,
            bonus_results=bonus_results,
            penalty_results=penalty_results
        )

        # Create custom feedback preferences
        feedback_config = {
            "general": {
                "report_title": "Test Report",
                "show_passed_tests": True,
                "add_report_summary": True,
                "online_content": [{
                    "url": "http://example.com/css-guide",
                    "description": "CSS Best Practices",
                    "linked_tests": ["failing_base_test"]
                }]
            },
            "default": {
                "category_headers": {
                    "base": "Core Requirements",
                    "bonus": "Extra Credit",
                    "penalty": "Areas for Improvement"
                }
            }
        }
        self.mock_feedback_prefs = FeedbackPreferences.from_dict(feedback_config)

    def test_report_header(self):
        """Tests if the report header is generated correctly."""
        reporter = DefaultReporter(self.mock_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        self.assertIn("# Test Report", feedback)
        self.assertIn("### Olá, **Jane Doe**! 👋", feedback)
        self.assertIn("> **Nota Final:** **`75.50 / 100`**", feedback)

    def test_report_sections_and_content(self):
        """
        Tests that each category section is correctly rendered based on feedback preferences.
        """
        reporter = DefaultReporter(self.mock_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        # Check for custom headers
        self.assertIn("## Core Requirements", feedback)
        self.assertIn("## Extra Credit", feedback)
        self.assertIn("## Areas for Improvement", feedback)

        # Base section should only show the failing test
        self.assertIn("failing_base_test", feedback)
        self.assertNotIn("passing_base_test", feedback)

        # Bonus section should only show the passing test (since show_passed_tests is True)
        self.assertIn("passing_bonus_test", feedback)
        self.assertNotIn("failing_bonus_test", feedback)

        # Penalty section should only show the failing (applied) penalty
        self.assertIn("failing_penalty_test", feedback)
        self.assertNotIn("passing_penalty_test", feedback)

    def test_parameter_formatting(self):
        """Tests if test parameters are formatted correctly in the report."""
        reporter = DefaultReporter(self.mock_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        # Check for the formatted parameter string in the failing base test
        self.assertIn("(Parâmetros: `file: 'style.css'`)", feedback)

    def test_summary_table_generation(self):
        """Tests the generation of the summary table with correct entries."""
        reporter = DefaultReporter(self.mock_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        self.assertIn("### 📝 Resumo dos Pontos de Atenção", feedback)
        # Should contain the failing base test and the failing penalty test
        self.assertIn("| Revisar | `css` | `failing_base_test` (Parâmetros: `file: 'style.css'`) |", feedback)
        self.assertIn("| Corrigir (Penalidade) | `js_malpractice` | `failing_penalty_test` |", feedback)
        # Should NOT contain any passing tests
        self.assertNotIn("passing_base_test", feedback.split("### 📝 Resumo dos Pontos de Atenção")[1])

    def test_online_content_linking(self):
        """Tests if suggested learning resources are correctly linked in the report."""
        reporter = DefaultReporter(self.mock_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        # The failing_base_test is linked to a resource, so it should be present
        expected_link = "> 📚 **Recurso Sugerido:** [CSS Best Practices](http://example.com/css-guide)"
        self.assertIn(expected_link, feedback)

    def test_no_issues_report(self):
        """Tests the report format when all tests pass and no penalties are applied."""
        # Create a result object with only passing scores
        all_passing_result = Result(
            final_score=100.0, author="John Doe", submission_file={},
            base_results=[TestResult("p1", 100, "p", "s1")],
            bonus_results=[TestResult("p2", 100, "p", "s2")],
            penalty_results=[]
        )
        reporter = DefaultReporter(all_passing_result, self.mock_feedback_prefs)
        feedback = reporter.generate_feedback()

        # No category sections for base/penalty should be generated
        self.assertNotIn("## Core Requirements", feedback)
        self.assertNotIn("## Areas for Improvement", feedback)

        # Summary should show the success message
        self.assertIn("Excelente trabalho! Nenhum ponto crítico de atenção foi encontrado.", feedback)


if __name__ == '__main__':
    unittest.main()
