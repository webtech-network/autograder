"""
Deliberate Code Execution Service.

This service provides stateless code execution without grading.
It uses the sandbox manager to execute code and return outputs.
"""

import asyncio

from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.manager import get_sandbox_manager
from sandbox_manager.models.sandbox_models import Language, ResponseCategory, CommandResponse
from web.config.logging import get_logger
from web.schemas.execution import DeliberateCodeExecutionRequest, DeliberateCodeExecutionResponse, DeliberateCodeExecutionResult


logger = get_logger(__name__)


def _get_error_message(result: CommandResponse) -> str:
    """
    Build error message based on response category.

    Args:
        result: CommandResponse from sandbox execution

    Returns:
        Error message string or None if successful
    """
    if result.category == ResponseCategory.SUCCESS:
        return None

    # Map category to error message
    error_messages = {
        ResponseCategory.COMPILATION_ERROR: "Compilation failed",
        ResponseCategory.RUNTIME_ERROR: "Runtime error occurred",
        ResponseCategory.TIMEOUT: "Execution timed out",
        ResponseCategory.SYSTEM_ERROR: "System error occurred",
    }

    error_message = error_messages.get(result.category)

    # Add stderr if available
    if result.stderr:
        if error_message:
            error_message = f"{error_message}: {result.stderr}"
        else:
            error_message = result.stderr

    return error_message


async def _execute_test_cases(
    sandbox,
    program_command: str,
    test_cases: list[list[str]]
) -> list[DeliberateCodeExecutionResult]:
    """Execute a list of test cases in the sandbox."""
    execution_results: list[DeliberateCodeExecutionResult] = []

    for idx, test_case_args in enumerate(test_cases):
        logger.info("Executing test case %d of %d", idx + 1, len(test_cases))

        result: CommandResponse

        if test_case_args:
            # Format/flatten inputs if they're provided as list of lists
            flattened_inputs = [str(input_args) for input_args in test_case_args]

            logger.info("Executing with %d input(s) for test case %d", len(flattened_inputs), idx + 1)
            result = await asyncio.to_thread(
                sandbox.run_commands,
                flattened_inputs,
                program_command,
                timeout=30,
                workdir="/app"
            )
        else:
            # No inputs, just run the command
            logger.info("Executing without inputs for test case %d", idx + 1)
            result = await asyncio.to_thread(
                sandbox.run_command,
                program_command,
                timeout=30,
                workdir="/app"
            )

        logger.info(
            "Test case %d completed: category=%s, exit_code=%d, time=%.3fs",
            idx + 1, result.category.value, result.exit_code, result.execution_time
        )

        # Build result item
        output_parts = [part for part in (result.stdout, result.stderr) if part]
        output = "\n".join(output_parts)
        error_message = _get_error_message(result)

        execution_results.append(
            DeliberateCodeExecutionResult(
                output=output,
                category=result.category,
                error_message=error_message,
                execution_time=result.execution_time
            )
        )

    return execution_results


async def execute_code(request: DeliberateCodeExecutionRequest) -> DeliberateCodeExecutionResponse:
    """
    Execute code in a sandbox without grading.

    This is a stateless operation - no data is persisted.

    Args:
        request: DeliberateCodeExecutionRequest containing language, files, command, and optional inputs

    Returns:
        DeliberateCodeExecutionResponse with output, category, error message, and execution time

    Raises:
        ValueError: If language is not supported or sandbox manager is not initialized
        Exception: If execution fails
    """
    logger.info("Deliberate execution request: language=%s, command=%s",
                request.language, request.program_command)

    # Convert language string to Language enum
    try:
        language = Language[request.language.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {request.language}") from exc

    # Get sandbox manager
    try:
        sandbox_manager = get_sandbox_manager()
    except ValueError as e:
        logger.error("Sandbox manager not initialized: %s", e)
        raise ValueError("Sandbox manager not available. Please contact system administrator.") from e

    # Acquire sandbox
    sandbox = None
    timed_out = False  # Track if execution timed out
    try:
        sandbox = sandbox_manager.get_sandbox(language)
        logger.info("Acquired sandbox for %s", language.value)

        # Convert submission files to the format expected by sandbox
        files_dict = {
            file_data.filename: SubmissionFile(
                filename=file_data.filename,
                content=file_data.content
            )
            for file_data in request.submission_files
        }

        # Prepare workdir with submission files
        sandbox.prepare_workdir(files_dict)
        logger.info("Prepared workdir with %d file(s)", len(files_dict))

        # Determine test cases to run (at least 1 empty run if none provided)
        test_cases = request.test_cases if request.test_cases else [[]]

        # Execute test cases
        execution_results = await _execute_test_cases(
            sandbox,
            request.program_command,
            test_cases
        )

        return DeliberateCodeExecutionResponse(results=execution_results)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Execution failed: %s", e, exc_info=True)
        # Return error response instead of raising
        return DeliberateCodeExecutionResponse(
            results=[
                DeliberateCodeExecutionResult(
                    output="",
                    category=ResponseCategory.SYSTEM_ERROR,
                    error_message=f"Execution failed: {str(e)}",
                    execution_time=0.0
                )
            ]
        )

    finally:
        # Release or destroy sandbox depending on timeout
        if sandbox:
            if timed_out:
                # Destroy sandbox instead of releasing it, since it's still running
                sandbox_manager.destroy_sandbox(language, sandbox)
                logger.info("Destroyed timed-out sandbox for %s", language.value)
            else:
                # Normal release back to pool
                sandbox_manager.release_sandbox(language, sandbox)
                logger.info("Released sandbox for %s", language.value)






