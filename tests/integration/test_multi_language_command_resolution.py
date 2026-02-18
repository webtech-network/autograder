"""Integration test for multi-language command resolution in the pipeline."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language


class TestMultiLanguageCommandResolution:
    """Test that the pipeline correctly resolves commands based on submission language."""

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_resolves_python_command(self, mock_get_manager):
        """Test that Python submissions get Python command."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = Mock()
        mock_output.stdout = "8"
        mock_output.stderr = ""
        mock_sandbox.run_commands.return_value = mock_output

        # Create pipeline
        pipeline = build_pipeline(
            template_name="input_output",
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
        execution = pipeline.run(submission)

        # Verify sandbox was called with Python command
        assert mock_sandbox.run_commands.called
        call_args = mock_sandbox.run_commands.call_args
        assert call_args[1]['program_command'] == "python3 calculator.py"

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_resolves_java_command(self, mock_get_manager):
        """Test that Java submissions get Java command."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = Mock()
        mock_output.stdout = "8"
        mock_output.stderr = ""
        mock_sandbox.run_commands.return_value = mock_output

        # Create pipeline
        pipeline = build_pipeline(
            template_name="input_output",
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
        execution = pipeline.run(submission)

        # Verify sandbox was called with Java command
        assert mock_sandbox.run_commands.called
        call_args = mock_sandbox.run_commands.call_args
        assert call_args[1]['program_command'] == "java Calculator"

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_resolves_cmd_placeholder(self, mock_get_manager):
        """Test that CMD placeholder auto-resolves based on language."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = Mock()
        mock_output.stdout = "8"
        mock_output.stderr = ""
        mock_sandbox.run_commands.return_value = mock_output

        # Create pipeline with CMD placeholder
        pipeline = build_pipeline(
            template_name="input_output",
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
        execution = pipeline.run(submission)

        # Verify sandbox was called with auto-resolved Node command
        assert mock_sandbox.run_commands.called
        call_args = mock_sandbox.run_commands.call_args
        # CMD should auto-resolve to default Node command
        assert "node" in call_args[1]['program_command']

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_handles_legacy_command_format(self, mock_get_manager):
        """Test backward compatibility with legacy single-command format."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command execution
        mock_output = Mock()
        mock_output.stdout = "8"
        mock_output.stderr = ""
        mock_sandbox.run_commands.return_value = mock_output

        # Create pipeline with legacy command format
        pipeline = build_pipeline(
            template_name="input_output",
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
                                    "value": "python3 calculator.py"  # Legacy format
                                }
                            ]
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        # Create submission (language doesn't matter for legacy format)
        files = {
            "calculator.py": SubmissionFile(
                filename="calculator.py",
                content="print('test')"
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
        execution = pipeline.run(submission)

        # Verify sandbox was called with the legacy command as-is
        assert mock_sandbox.run_commands.called
        call_args = mock_sandbox.run_commands.call_args
        assert call_args[1]['program_command'] == "python3 calculator.py"

    @patch('autograder.services.pre_flight_service.get_sandbox_manager')
    def test_pipeline_grading_with_multi_language_commands(self, mock_get_manager):
        """Test full grading flow with multi-language commands."""
        # Mock sandbox
        mock_manager = Mock()
        mock_sandbox = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_sandbox.return_value = mock_sandbox
        mock_sandbox.prepare_workdir.return_value = None

        # Mock command executions (2 tests)
        mock_output1 = Mock()
        mock_output1.stdout = "8"
        mock_output1.stderr = ""

        mock_output2 = Mock()
        mock_output2.stdout = "14"
        mock_output2.stderr = ""

        mock_sandbox.run_commands.side_effect = [mock_output1, mock_output2]

        # Create pipeline with multiple tests
        pipeline = build_pipeline(
            template_name="input_output",
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
        assert mock_sandbox.run_commands.call_count == 2
        call1 = mock_sandbox.run_commands.call_args_list[0]
        call2 = mock_sandbox.run_commands.call_args_list[1]

        assert call1[1]['program_command'] == "./calc"
        assert call2[1]['program_command'] == "./calc"

        # Verify final score is 100 (both tests passed)
        assert execution.result is not None
        assert execution.result.final_score == 100.0

