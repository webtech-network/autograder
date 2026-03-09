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
from web.schemas.execution import DeliberateCodeExecutionRequest, DeliberateCodeExecutionResponse


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

        # Execute code with timeout
        # Note: The timeout parameter passed to run_command/run_commands is not enforced by Docker
        # So we use asyncio.wait_for to enforce the timeout at the application level
        execution_timeout = 30  # seconds
        result: CommandResponse

        try:
            if request.inputs:
                # Flatten inputs if they're provided as list of lists
                # Each inner list represents arguments for a single input line
                flattened_inputs = []
                for input_args in request.inputs:
                    # Join arguments with spaces if multiple args per line
                    flattened_inputs.append(' '.join(input_args) if isinstance(input_args, list) else str(input_args))

                logger.info("Executing with %d input(s)", len(flattened_inputs))
                # Use run_commands for interactive input with timeout enforcement
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        sandbox.run_commands,
                        flattened_inputs,
                        request.program_command,
                        timeout=execution_timeout,
                        workdir="/app"
                    ),
                    timeout=execution_timeout
                )
            else:
                # No inputs, just run the command with timeout enforcement
                logger.info("Executing without inputs")
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        sandbox.run_command,
                        request.program_command,
                        timeout=execution_timeout,
                        workdir="/app"
                    ),
                    timeout=execution_timeout
                )
        except asyncio.TimeoutError:
            # Execution exceeded timeout - mark for destruction
            timed_out = True
            logger.warning("Execution timed out after %d seconds, sandbox will be destroyed", execution_timeout)
            result = CommandResponse(
                stdout='',
                stderr=f'Execution timed out after {execution_timeout} seconds',
                exit_code=124,  # Standard timeout exit code
                execution_time=execution_timeout,
                category=ResponseCategory.TIMEOUT
            )

        logger.info(
            "Execution completed: category=%s, exit_code=%d, time=%.3fs",
            result.category.value, result.exit_code, result.execution_time
        )

        # Build response
        # Combine stdout and stderr so callers see all output (e.g. output before a crash)
        output_parts = [part for part in (result.stdout, result.stderr) if part]
        output = "\n".join(output_parts)
        error_message = _get_error_message(result)

        return DeliberateCodeExecutionResponse(
            output=output,
            category=result.category,
            error_message=error_message,
            execution_time=result.execution_time
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Execution failed: %s", e, exc_info=True)
        # Return error response instead of raising
        return DeliberateCodeExecutionResponse(
            output="",
            category=ResponseCategory.SYSTEM_ERROR,
            error_message=f"Execution failed: {str(e)}",
            execution_time=0.0
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






