import pytest
from unittest.mock import MagicMock

from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.dataclass.preflight_error import PreflightCheckType, PreflightError
from autograder.serializers.pipeline_execution_serializer import PipelineExecutionSerializer


def test_serialize_legacy_file_missing_error():
    # Setup
    execution = MagicMock()
    execution.start_time = 0
    execution.status.value = "failed"
    
    # Mock StepResult for file missing error
    mock_error_data = [
        PreflightError(
            type=PreflightCheckType.FILE_CHECK,
            message="Arquivo ou diretório obrigatório não encontrado: `\'Main.java\'`",
            details={"missing_file": "Main.java"}
        )
    ]
    
    step_result = StepResult.fail(
        step=StepName.PRE_FLIGHT,
        error="Arquivo ou diretório obrigatório não encontrado: `\'Main.java\'`",
        error_data=mock_error_data
    )
    
    execution.step_results = [step_result]
    
    # Execute
    summary = PipelineExecutionSerializer.serialize(execution)
    
    # Assert
    assert summary["status"] == "failed"
    assert summary["failed_at_step"] == "PreFlightStep"
    
    preflight_step = summary["steps"][0]
    assert preflight_step["name"] == "PreFlightStep"
    assert preflight_step["status"] == "fail"
    assert preflight_step["error_details"] == {
        "error_type": "required_file_missing",
        "phase": "required_files",
        "missing_file": "Main.java"
    }


def test_serialize_setup_command_failed():
    # Setup
    execution = MagicMock()
    execution.start_time = 0
    execution.status.value = "failed"
    
    # Mock StepResult for setup command failure
    mock_error_data = [
        PreflightError(
            type=PreflightCheckType.SETUP_COMMAND,
            message="Setup command \'Compile\' failed...",
            details={
                "command_name": "Compile",
                "command": "javac Main.java",
                "exit_code": 1,
                "stdout": "",
                "stderr": "error: cannot find symbol"
            }
        )
    ]
    
    step_result = StepResult.fail(
        step=StepName.PRE_FLIGHT,
        error="Setup command \'Compile\' failed...",
        error_data=mock_error_data
    )
    
    execution.step_results = [step_result]
    
    # Execute
    summary = PipelineExecutionSerializer.serialize(execution)
    
    # Assert
    assert summary["status"] == "failed"
    assert summary["failed_at_step"] == "PreFlightStep"
    
    preflight_step = summary["steps"][0]
    assert preflight_step["name"] == "PreFlightStep"
    assert preflight_step["status"] == "fail"
    assert preflight_step["error_details"] == {
        "error_type": "setup_command_failed",
        "phase": "setup_commands",
        "command_name": "Compile",
        "failed_command": {
            "command": "javac Main.java",
            "exit_code": 1,
            "stdout": "",
            "stderr": "error: cannot find symbol"
        }
    }


def test_serialize_skips_bootstrap_step():
    # Setup
    execution = MagicMock()
    execution.start_time = 0
    execution.status.value = "running"
    
    bootstrap = StepResult.success(StepName.BOOTSTRAP, data=None)
    load = StepResult.success(StepName.LOAD_TEMPLATE, data=None)
    
    execution.step_results = [bootstrap, load]
    
    # Execute
    summary = PipelineExecutionSerializer.serialize(execution)
    
    # Assert
    assert len(summary["steps"]) == 1
    assert summary["steps"][0]["name"] == "LoadTemplateStep"
