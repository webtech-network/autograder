"""Integration test for multi-language command resolution in the pipeline."""

from unittest.mock import Mock, patch

from tests.integration.definition_fixtures import build_migrated_fixture_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from tests.process_results import exited
from autograder.models.language import Language


class TestMultiLanguageCommandResolution:
    """Test that the pipeline correctly resolves commands based on submission language."""

    @patch('tests.integration.sandbox_support.current_test_manager')
    def test_pipeline_resolves_python_command(self, mock_get_manager):
        """Test that Python submissions get Python command."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.acquire.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = exited("8")
        mock_sandbox.run_process.return_value = mock_output

        # Create pipeline
        pipeline = build_migrated_fixture_pipeline(
            template_name="input_output",
            languages=["python", "java", "node", "cpp"],
            include_feedback=False,
            grading_criteria={
                "test_library": "input_output",
                "base": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calculator.py",
                                        "java": "java Calculator",
                                        "node": "node calculator.js",
                                        "cpp": "./calculator"
                                    }
                                }
                            ]
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        # Create Python submission
        files = {
            "calculator.py": SubmissionFile(
                filename="calculator.py",
                content="a = int(input())\nb = int(input())\nprint(a + b)"
            )
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.PYTHON
        )

        # Run pipeline
        pipeline.run(submission)

        # Verify sandbox was called with Python command
        assert mock_sandbox.run_process.called
        call_args = mock_sandbox.run_process.call_args
        assert " ".join(call_args.args[0].argv) == "python3 calculator.py"

    @patch('tests.integration.sandbox_support.current_test_manager')
    def test_pipeline_resolves_java_command(self, mock_get_manager):
        """Test that Java submissions get Java command."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.acquire.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = exited("8")
        mock_sandbox.run_process.return_value = mock_output

        # Create pipeline
        pipeline = build_migrated_fixture_pipeline(
            template_name="input_output",
            languages=["python", "java", "node", "cpp"],
            include_feedback=False,
            grading_criteria={
                "test_library": "input_output",
                "base": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calculator.py",
                                        "java": "java Calculator",
                                        "node": "node calculator.js",
                                        "cpp": "./calculator"
                                    }
                                }
                            ]
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        # Create Java submission
        files = {
            "Calculator.java": SubmissionFile(
                filename="Calculator.java",
                content="public class Calculator { }"
            )
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.JAVA
        )

        # Run pipeline
        pipeline.run(submission)

        # Verify sandbox was called with Java command
        assert mock_sandbox.run_process.called
        call_args = mock_sandbox.run_process.call_args
        assert " ".join(call_args.args[0].argv) == "java Calculator"

    @patch('tests.integration.sandbox_support.current_test_manager')
    def test_pipeline_resolves_cmd_placeholder(self, mock_get_manager):
        """Test that CMD placeholder auto-resolves based on language."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.acquire.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = exited("8")
        mock_sandbox.run_process.return_value = mock_output

        # Create pipeline with CMD placeholder
        pipeline = build_migrated_fixture_pipeline(
            template_name="input_output",
            languages=["python", "java", "node", "cpp"],
            include_feedback=False,
            grading_criteria={
                "test_library": "input_output",
                "base": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {"name": "program_command", "value": "CMD"}
                            ]
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        # Create Node submission
        files = {
            "calculator.js": SubmissionFile(
                filename="calculator.js",
                content="console.log('test')"
            )
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.NODE
        )

        # Run pipeline
        pipeline.run(submission)

        # Verify sandbox was called with auto-resolved Node command
        assert mock_sandbox.run_process.called
        call_args = mock_sandbox.run_process.call_args
        # CMD should auto-resolve to default Node command
        assert "node" in " ".join(call_args.args[0].argv)

    @patch('tests.integration.sandbox_support.current_test_manager')
    def test_pipeline_grading_with_multi_language_commands(self, mock_get_manager):
        """Test full grading flow with multi-language commands."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.acquire.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command executions (2 tests)
        mock_output1 = exited("8")

        mock_output2 = exited("14")

        mock_sandbox.run_process.side_effect = [mock_output1, mock_output2]

        # Create pipeline with multiple tests
        pipeline = build_migrated_fixture_pipeline(
            template_name="input_output",
            languages=["python", "java", "node", "cpp"],
            include_feedback=False,
            grading_criteria={
                "test_library": "input_output",
                "base": {
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calc.py",
                                        "java": "java Calc",
                                        "node": "node calc.js",
                                        "cpp": "./calc"
                                    }
                                }
                            ]
                        },
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["10", "4"]},
                                {"name": "expected_output", "value": "14"},
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calc.py",
                                        "java": "java Calc",
                                        "node": "node calc.js",
                                        "cpp": "./calc"
                                    }
                                }
                            ]
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        # Create C++ submission
        files = {
            "calc.cpp": SubmissionFile(
                filename="calc.cpp",
                content="#include <iostream>\nint main() { return 0; }"
            )
        }

        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files=files,
            language=Language.CPP
        )

        # Run pipeline
        execution = pipeline.run(submission)

        # Verify both tests used C++ command
        assert mock_sandbox.run_process.call_count == 2
        call1 = mock_sandbox.run_process.call_args_list[0]
        call2 = mock_sandbox.run_process.call_args_list[1]

        assert " ".join(call1.args[0].argv) == "./calc"
        assert " ".join(call2.args[0].argv) == "./calc"

        # Verify final score is 100 (both tests passed)
        assert execution.outcome.tree is not None
        assert execution.outcome.score == 100.0

