import unittest
from unittest.mock import MagicMock, patch
from autograder.autograder import build_pipeline
from autograder.models.dataclass.step_result import StepName
from autograder.models.abstract.template import Template

class TestIssue331PipelineBuilder(unittest.TestCase):
    def setUp(self):
        self.config = {
            "template_name": "test_template",
            "include_feedback": False,
            "grading_criteria": {"base": []},
            "feedback_config": {},
        }

    @patch("autograder.autograder.TemplateLibraryService")
    def test_build_pipeline_minimal_steps(self, mock_template_service_class):
        # Mock TemplateLibraryService and Template
        mock_service = mock_template_service_class.get_instance.return_value
        mock_template = MagicMock(spec=Template)
        mock_template.requires_sandbox = False
        mock_template.required_files = {}
        mock_template.setup_commands = {}
        mock_template.get_tests.return_value = {} # No AI tests
        mock_service.load_builtin_template.return_value = mock_template
        
        # Build pipeline
        pipeline = build_pipeline(
            template_name="test_template",
            include_feedback=False,
            grading_criteria={"base": []},
            feedback_config={},
            setup_config=None
        )
        
        # Check steps
        step_names = list(pipeline._steps.keys())
        
        # Should NOT include SANDBOX, FILE_CHECK, ASSET_INJECTION, SETUP_COMMANDS, AI_BATCH
        self.assertIn(StepName.LOAD_TEMPLATE, step_names)
        self.assertIn(StepName.BUILD_TREE, step_names)
        self.assertIn(StepName.GRADE, step_names)
        
        self.assertNotIn(StepName.SANDBOX, step_names)
        self.assertNotIn(StepName.FILE_CHECK, step_names)
        self.assertNotIn(StepName.ASSET_INJECTION, step_names)
        self.assertNotIn(StepName.SETUP_COMMANDS, step_names)
        self.assertNotIn(StepName.AI_BATCH, step_names)

    @patch("autograder.autograder.TemplateLibraryService")
    def test_build_pipeline_with_sandbox(self, mock_template_service_class):
        # Mock Template requiring sandbox
        mock_service = mock_template_service_class.get_instance.return_value
        mock_template = MagicMock(spec=Template)
        mock_template.requires_sandbox = True
        mock_template.required_files = {}
        mock_template.setup_commands = {}
        mock_template.get_tests.return_value = {}
        mock_service.load_builtin_template.return_value = mock_template
        
        pipeline = build_pipeline(
            template_name="test_template",
            include_feedback=False,
            grading_criteria={"base": []},
            feedback_config={}
        )
        
        step_names = list(pipeline._steps.keys())
        self.assertIn(StepName.SANDBOX, step_names)
        # FILE_CHECK is still not included if no setup_config
        self.assertNotIn(StepName.FILE_CHECK, step_names)

    @patch("autograder.autograder.TemplateLibraryService")
    def test_build_pipeline_with_setup_config(self, mock_template_service_class):
        # Mock Template NOT requiring sandbox
        mock_service = mock_template_service_class.get_instance.return_value
        mock_template = MagicMock(spec=Template)
        mock_template.requires_sandbox = False
        mock_template.required_files = {}
        mock_template.setup_commands = {}
        mock_template.get_tests.return_value = {}
        mock_service.load_builtin_template.return_value = mock_template
        
        pipeline = build_pipeline(
            template_name="test_template",
            include_feedback=False,
            grading_criteria={"base": []},
            feedback_config={},
            setup_config={"python": {"required_files": ["main.py"]}}
        )
        
        step_names = list(pipeline._steps.keys())
        self.assertIn(StepName.FILE_CHECK, step_names)
        self.assertNotIn(StepName.PRE_FLIGHT, step_names)

    @patch("autograder.autograder.TemplateLibraryService")
    def test_build_pipeline_with_ai(self, mock_template_service_class):
        from autograder.models.abstract.ai_test_function import AiTestFunction
        
        # Mock Template with AI test
        mock_service = mock_template_service_class.get_instance.return_value
        mock_template = MagicMock(spec=Template)
        mock_template.requires_sandbox = False
        
        mock_ai_test = MagicMock(spec=AiTestFunction)
        mock_template.get_tests.return_value = {"ai_test": mock_ai_test}
        
        mock_service.load_builtin_template.return_value = mock_template
        
        pipeline = build_pipeline(
            template_name="test_template",
            include_feedback=False,
            grading_criteria={"base": []},
            feedback_config={}
        )
        
        step_names = list(pipeline._steps.keys())
        self.assertIn(StepName.AI_BATCH, step_names)

if __name__ == "__main__":
    unittest.main()
