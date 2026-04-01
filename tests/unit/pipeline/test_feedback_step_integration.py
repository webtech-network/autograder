import unittest
from unittest.mock import MagicMock
from autograder.steps.feedback_step import FeedbackStep
from autograder.services.report.reporter_service import ReporterService
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.submission import Submission
from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.focus import Focus

class TestFeedbackStepIntegration(unittest.TestCase):
    """Integration tests for the FeedbackStep."""
    def test_feedback_step_execute(self):
        """Tests the execution of FeedbackStep and its integration with ReporterService."""
        # Setup
        feedback_mode = "default"
        reporter_service = ReporterService(feedback_mode=feedback_mode)
        feedback_config = {
            "general": {"report_title": "Integration Test Title"}
        }
        step = FeedbackStep(reporter_service, feedback_config)
        
        # Mock PipelineExecution and Submission
        submission = MagicMock(spec=Submission)
        submission.user_id = "test_user"
        submission.assignment_id = 1
        submission.language = MagicMock()
        submission.language.value = "python"
        pipeline_exec = PipelineExecution.start_execution(submission)
        
        # Add a mock FOCUS result
        focused_tests = Focus(base=[], penalty=[], bonus=[])
        focus_result = StepResult(
            step=StepName.FOCUS,
            data=focused_tests,
            status=StepStatus.SUCCESS
        )
        pipeline_exec.add_step_result(focus_result)

        # Add a mock GRADE result
        grade_result = MagicMock()
        grade_result.final_score = 100.0
        grade_result.result_tree = MagicMock()
        grade_result.result_tree.template_name = "test_template"
        grade_result.result_tree.root.score = 100.0
        
        grade_step_result = StepResult(
            step=StepName.GRADE,
            data=grade_result,
            status=StepStatus.SUCCESS
        )
        pipeline_exec.add_step_result(grade_step_result)
        
        # Execute
        updated_pipeline_exec = step.execute(pipeline_exec)
        
        # Verify
        feedback_result = updated_pipeline_exec.get_step_result(StepName.FEEDBACK)
        self.assertIsNotNone(feedback_result)
        self.assertEqual(feedback_result.status, StepStatus.SUCCESS)
        self.assertIn("Integration Test Title", feedback_result.data)
        self.assertIn("GRADING SUMMARY", feedback_result.data)
        
        # Check if ReporterService was used
        # (Implicitly checked by the data being "Default report generated.")

if __name__ == "__main__":
    unittest.main()
