import time
from typing import Dict, Any

from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus
from autograder.models.dataclass.preflight_error import PreflightCheckType


class PipelineExecutionSerializer:
    """
    Handles the serialization of PipelineExecution into dictionary payloads
    suitable for API responses and analytical views.
    """

    @classmethod
    def serialize(cls, execution: PipelineExecution) -> Dict[str, Any]:
        """
        Generate a detailed summary of the pipeline execution for API responses.

        Returns:
            Dictionary containing execution status, steps, and error details
        """
        execution_time_ms = int((time.time() - execution.start_time) * 1000) if execution.start_time else 0

        # Determine failed step if any
        failed_step = None
        for step in execution.step_results:
            if step.status == StepStatus.FAIL:
                failed_step = step.step.value
                break

        # Build step details
        steps = []
        for step in execution.step_results:
            if step.step == StepName.BOOTSTRAP:
                continue  # Skip bootstrap step in output

            step_info = {
                "name": step.step.value,
                "status": step.status.value,
            }

            # Add execution time if available
            if hasattr(step, 'execution_time_ms'):
                step_info["execution_time_ms"] = step.execution_time_ms

            # Add success message for completed steps
            if step.status == StepStatus.SUCCESS:
                step_info["message"] = cls._get_success_message(step, execution)

            # Add error details for failed steps
            elif step.status == StepStatus.FAIL and step.error:
                step_info["message"] = step.error.split('\n')[0]  # First line of error
                step_info["error_details"] = cls._extract_error_details(step)

            steps.append(step_info)

        # Count planned vs completed steps
        total_planned = 7  # BOOTSTRAP, LOAD_TEMPLATE, BUILD_TREE, PRE_FLIGHT, GRADE, FEEDBACK, EXPORT
        completed = len([s for s in execution.step_results if s.step != StepName.BOOTSTRAP])

        return {
            "status": execution.status.value if execution.status != PipelineStatus.EMPTY else "unknown",
            "failed_at_step": failed_step,
            "total_steps_planned": total_planned,
            "steps_completed": completed,
            "execution_time_ms": execution_time_ms,
            "steps": steps
        }

    @classmethod
    def _get_success_message(cls, step: StepResult, execution: PipelineExecution) -> str:
        """Returns success message for a specific pipeline step."""
        if step.step == StepName.LOAD_TEMPLATE:
            return "Template loaded successfully"
        elif step.step == StepName.BUILD_TREE:
            return "Criteria tree built successfully"
        elif step.step == StepName.PRE_FLIGHT:
            return "All preflight checks passed"
        elif step.step == StepName.GRADE:
            if execution.result and execution.result.final_score is not None:
                return f"Grading completed: {execution.result.final_score}/100"
            return "Grading completed"
        elif step.step == StepName.FEEDBACK:
            return "Feedback generated"
        elif step.step == StepName.EXPORTER:
            return "Results exported"
        return ""

    @classmethod
    def _extract_error_details(cls, step: StepResult) -> Dict[str, Any]:
        """
        Extract structured error details from a failed step using its structured error_data.
        This provides backward compatibility with the legacy text-based regex parser.
        """
        error_details = {}

        if step.step == StepName.PRE_FLIGHT and step.error_data:
            # error_data is a list of PreflightError objects. 
            # We map properties from the first critical error for legacy backward compatibility.
            if isinstance(step.error_data, list) and len(step.error_data) > 0:
                first_error = step.error_data[0]
                
                # Check for Dictionary or Object access depending on how it's passed at runtime
                err_type = first_error.type if hasattr(first_error, 'type') else first_error.get('type')
                err_details = first_error.details if hasattr(first_error, 'details') else first_error.get('details', {})

                if err_type == PreflightCheckType.FILE_CHECK:
                    error_details["error_type"] = "required_file_missing"
                    error_details["phase"] = "required_files"
                    if err_details and "missing_file" in err_details:
                        error_details["missing_file"] = err_details["missing_file"]
                        
                elif err_type == PreflightCheckType.SETUP_COMMAND:
                    error_details["error_type"] = "setup_command_failed"
                    error_details["phase"] = "setup_commands"
                    if err_details:
                        if "command_name" in err_details:
                            error_details["command_name"] = err_details["command_name"]
                            
                        failed_command = {}
                        if "command" in err_details:
                            failed_command["command"] = err_details["command"]
                        if "exit_code" in err_details:
                            failed_command["exit_code"] = err_details["exit_code"]
                        if "stderr" in err_details:
                            failed_command["stderr"] = err_details["stderr"]
                        if "stdout" in err_details:
                            failed_command["stdout"] = err_details["stdout"]
                            
                        # Preserve legacy nested structure
                        if failed_command:
                            error_details["failed_command"] = failed_command

        return error_details
