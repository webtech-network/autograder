import unittest
from unittest.mock import patch, MagicMock

# It's good practice to import the module/class you are testing
from autograder.autograder_facade import Autograder
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.result import Result


class TestAutograderFacade(unittest.TestCase):

    def setUp(self):
        """Set up mock data that can be used across multiple tests."""
        self.mock_submission = {"file.py": "print('hello')"}
        self.mock_criteria = {"base": {"subjects": {"test": {"tests": ["passing_test"]}}}}
        self.mock_feedback_prefs = {"general": {}}

        self.mock_assignment_config = AssignmentConfig(
            criteria=self.mock_criteria,
            feedback=self.mock_feedback_prefs,
            setup=None,
            template="web dev"
        )

        # A standard successful result from the Grader
        self.mock_grader_result = Result(
            final_score=85.0,
            author="test_student",
            submission_file=self.mock_submission,
            base_results=[], bonus_results=[], penalty_results=[]
        )

    @patch('autograder.autograder_facade.CriteriaTree')
    @patch('autograder.autograder_facade.TemplateLibrary')
    @patch('autograder.autograder_facade.Grader')
    @patch('autograder.autograder_facade.Reporter')
    def test_grade_success_default_feedback(self, mock_reporter, mock_grader, mock_template_library,
                                            mock_criteria_tree):
        """
        Tests a successful grading process using the default feedback mode.
        """
        # --- Arrange ---
        # Configure mocks to simulate a successful run
        mock_grader.return_value.run.return_value = self.mock_grader_result
        mock_reporter.create_default_reporter.return_value.generate_feedback.return_value = "Great job!"

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student",
            feedback_mode="default"
        )

        # --- Act ---
        response = Autograder.grade(autograder_request)

        # --- Assert ---
        self.assertIsInstance(response, AutograderResponse)
        self.assertEqual(response.status, "Success")
        self.assertEqual(response.final_score, 85.0)
        self.assertEqual(response.feedback, "Great job!")

        # Verify that the core components were called
        mock_criteria_tree.build.assert_called_once_with(self.mock_criteria)
        mock_template_library.get_template.assert_called_once_with("web dev")
        mock_grader.return_value.run.assert_called_once()
        mock_reporter.create_default_reporter.assert_called_once()

    def test_grade_failure_invalid_template(self):
        """
        Tests the facade's response when an unsupported template name is provided.
        """
        # --- Arrange ---
        invalid_config = AssignmentConfig(self.mock_criteria, self.mock_feedback_prefs, None,
                                          template="invalid_template")
        autograder_request = AutograderRequest(self.mock_submission, invalid_config, "student")

        # --- Act ---
        response = Autograder.grade(autograder_request)

        # --- Assert ---
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("Unsupported template: invalid_template", response.feedback)

    @patch('autograder.autograder_facade.Grader')
    def test_grade_failure_during_grading(self, mock_grader):
        """
        Tests the facade's exception handling when the Grader class fails.
        """
        # --- Arrange ---
        mock_grader.return_value.run.side_effect = Exception("Something went wrong in the grader")

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student"
        )

        # --- Act ---
        response = Autograder.grade(autograder_request)

        # --- Assert ---
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("Something went wrong in the grader", response.feedback)

    @patch('autograder.autograder_facade.Grader')
    @patch('autograder.autograder_facade.Driver')
    @patch('autograder.autograder_facade.Reporter')
    def test_grade_failure_ai_missing_credentials(self, mock_reporter, mock_driver, mock_grader):
        """
        Tests that AI feedback mode fails correctly if essential keys are missing.
        """
        # --- Arrange ---
        mock_grader.return_value.run.return_value = self.mock_grader_result

        # Request AI feedback but provide no keys
        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student",
            feedback_mode="ai",
            openai_key=None  # Explicitly None
        )

        # --- Act ---
        response = Autograder.grade(autograder_request)

        # --- Assert ---
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("OpenAI key, Redis URL, and Redis token are required", response.feedback)


if __name__ == '__main__':
    unittest.main()
