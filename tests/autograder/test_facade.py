import unittest
from unittest.mock import patch, Mock

from autograder.pipeline.autograder_facade import Autograder
from autograder.models.autograder_request import AutograderRequest
from autograder.models.assignment_config import AssignmentConfig
from autograder.models.dataclass.autograder_response import AutograderResponse
from autograder.models.dataclass.result import Result


class TestAutograderFacade(unittest.TestCase):

    def setUp(self):
        # Common test data
        self.mock_submission = {"file.py": "print('hello')"}
        self.mock_criteria = {"base": {"subjects": {"test": {"tests": ["passing_test"]}}}}
        self.mock_feedback_prefs = {"general": {}}

        self.mock_assignment_config = AssignmentConfig(
            criteria=self.mock_criteria,
            feedback=self.mock_feedback_prefs,
            setup={},
            template="web dev"
        )

        # A standard successful result from the Grader
        self.mock_grader_result = Result(
            final_score=85.0,
            author="test_student",
            submission_file=self.mock_submission,
            base_results=[], bonus_results=[], penalty_results=[]
        )

    @patch('pipeline.autograder_facade.CriteriaTree')
    @patch('pipeline.autograder_facade.TemplateLibrary')
    @patch('pipeline.autograder_facade.Grader')
    @patch('pipeline.autograder_facade.Reporter')
    def test_grade_success_default_feedback(self, mock_reporter, mock_grader, mock_template_library,
                                            mock_criteria_tree):
        """A successful grading run that returns generated default feedback."""
        # Arrange
        # Create a fake template object with the attributes the facade expects
        fake_template = Mock()
        fake_template.requires_pre_executed_tree = False
        fake_template.template_name = "web dev"
        fake_template.stop = Mock()

        mock_template_library.get_template.return_value = fake_template

        fake_tree = Mock()
        fake_tree.print_pre_executed_tree = Mock()
        mock_criteria_tree.build_non_executed_tree.return_value = fake_tree

        mock_grader.return_value.run.return_value = self.mock_grader_result

        fake_reporter = Mock()
        fake_reporter.generate_feedback.return_value = "Great job!"
        mock_reporter.create_default_reporter.return_value = fake_reporter

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student",
            include_feedback=True,
            feedback_mode="default"
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertIsInstance(response, AutograderResponse)
        self.assertEqual(response.status, "Success")
        self.assertEqual(response.final_score, 85.0)
        self.assertEqual(response.feedback, "Great job!")

        mock_template_library.get_template.assert_called_once_with("web dev")
        mock_criteria_tree.build_non_executed_tree.assert_called_once()
        mock_grader.return_value.run.assert_called_once()
        mock_reporter.create_default_reporter.assert_called_once()

    @patch('pipeline.autograder_facade.TemplateLibrary')
    def test_grade_failure_invalid_template(self, mock_template_library):
        """If TemplateLibrary returns None, the facade should fail with an informative message."""
        # Arrange
        mock_template_library.get_template.return_value = None

        invalid_config = AssignmentConfig(
            criteria = self.mock_criteria,
            feedback = self.mock_feedback_prefs,
            setup = {},
            template="invalid template"
        )
        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=invalid_config,
            student_name="student"
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("Unsupported template: invalid template", response.feedback)

    @patch('pipeline.autograder_facade.CriteriaTree')
    @patch('pipeline.autograder_facade.TemplateLibrary')
    @patch('pipeline.autograder_facade.Grader')
    def test_grade_failure_during_grading(self, mock_grader, mock_template_library, mock_criteria_tree):
        """If the Grader raises an exception the facade should return a failure response containing the error."""
        # Arrange
        fake_template = Mock()
        fake_template.requires_pre_executed_tree = False
        fake_template.template_name = "web dev"
        fake_template.stop = Mock()
        mock_template_library.get_template.return_value = fake_template

        fake_tree = Mock()
        fake_tree.print_pre_executed_tree = Mock()
        mock_criteria_tree.build_non_executed_tree.return_value = fake_tree

        mock_grader.return_value.run.side_effect = Exception("Something went wrong in the grader")

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student"
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("Something went wrong in the grader", response.feedback)

    @patch('pipeline.autograder_facade.CriteriaTree')
    @patch('pipeline.autograder_facade.TemplateLibrary')
    @patch('pipeline.autograder_facade.Grader')
    def test_grade_failure_ai_missing_credentials(self, mock_grader, mock_template_library, mock_criteria_tree):
        """AI feedback mode without the required keys should fail with an explanatory message."""
        # Arrange
        fake_template = Mock()
        fake_template.requires_pre_executed_tree = False
        fake_template.template_name = "web dev"
        fake_template.stop = Mock()
        mock_template_library.get_template.return_value = fake_template

        fake_tree = Mock()
        fake_tree.print_pre_executed_tree = Mock()
        mock_criteria_tree.build_non_executed_tree.return_value = fake_tree

        mock_grader.return_value.run.return_value = self.mock_grader_result

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student",
            include_feedback=True,
            feedback_mode="ai",
            openai_key=None  # missing keys
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn("OpenAI key, Redis URL, and Redis token are required", response.feedback)

    @patch('pipeline.autograder_facade.PreFlight')
    def test_preflight_failure_stops_processing(self, mock_preflight):
        """If pre-flight returns impediments, grading should stop and return those messages."""
        # Arrange
        mock_preflight.run.return_value = [{'message': 'setup failed due to X'}]

        config_with_setup = AssignmentConfig(
             criteria=self.mock_criteria,
             feedback=self.mock_feedback_prefs,
             setup={'cmds': []},
             template="web dev"
        )
        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=config_with_setup,
            student_name="student"
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertEqual(response.status, "fail")
        self.assertEqual(response.final_score, 0.0)
        self.assertIn('setup failed due to X', response.feedback)

    @patch('pipeline.autograder_facade.CriteriaTree')
    @patch('pipeline.autograder_facade.TemplateLibrary')
    @patch('pipeline.autograder_facade.Grader')
    def test_no_feedback_requested_returns_score_only(self, mock_grader, mock_template_library, mock_criteria_tree):
        """When include_feedback is False, the facade should return the score and an empty feedback string."""
        # Arrange
        fake_template = Mock()
        fake_template.requires_pre_executed_tree = False
        fake_template.template_name = "web dev"
        fake_template.stop = Mock()
        mock_template_library.get_template.return_value = fake_template

        fake_tree = Mock()
        fake_tree.print_pre_executed_tree = Mock()
        mock_criteria_tree.build_non_executed_tree.return_value = fake_tree

        mock_grader.return_value.run.return_value = self.mock_grader_result

        autograder_request = AutograderRequest(
            submission_files=self.mock_submission,
            assignment_config=self.mock_assignment_config,
            student_name="test_student",
            include_feedback=False
        )

        # Act
        response = Autograder.grade(autograder_request)

        # Assert
        self.assertEqual(response.status, "Success")
        self.assertEqual(response.final_score, 85.0)
        self.assertEqual(response.feedback, "")


if __name__ == '__main__':
    unittest.main()
