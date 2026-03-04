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
    logger.info(f"Deliberate execution request: language={request.language}, command={request.program_command}")

    # Convert language string to Language enum
    try:
        language = Language[request.language.upper()]
    except KeyError:
        raise ValueError(f"Unsupported language: {request.language}")

    # Get sandbox manager
    try:
        sandbox_manager = get_sandbox_manager()
    except ValueError as e:
        logger.error(f"Sandbox manager not initialized: {e}")
        raise ValueError("Sandbox manager not available. Please contact system administrator.")

    # Acquire sandbox
    sandbox = None
    try:
        sandbox = sandbox_manager.get_sandbox(language)
        logger.info(f"Acquired sandbox for {language.value}")

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
        logger.info(f"Prepared workdir with {len(files_dict)} file(s)")

        # Execute code
        result: CommandResponse

        if request.inputs:
            # Flatten inputs if they're provided as list of lists
            # Each inner list represents arguments for a single input line
            flattened_inputs = []
            for input_args in request.inputs:
                # Join arguments with spaces if multiple args per line
                flattened_inputs.append(' '.join(input_args) if isinstance(input_args, list) else str(input_args))

            logger.info(f"Executing with {len(flattened_inputs)} input(s)")
            # Use run_commands for interactive input
            result = await asyncio.to_thread(
                sandbox.run_commands,
                flattened_inputs,
                request.program_command,
                timeout=30,
                workdir="/app"
            )
        else:
            # No inputs, just run the command
            logger.info("Executing without inputs")
            result = await asyncio.to_thread(
                sandbox.run_command,
                request.program_command,
                timeout=30,
                workdir="/app"
            )

        logger.info(
            f"Execution completed: category={result.category.value}, "
            f"exit_code={result.exit_code}, time={result.execution_time:.3f}s"
        )

        # Build response
        output = result.stdout if result.stdout else result.stderr
        error_message = None

        # Set error message based on category
        if result.category != ResponseCategory.SUCCESS:
            if result.category == ResponseCategory.COMPILATION_ERROR:
                error_message = "Compilation failed"
            elif result.category == ResponseCategory.RUNTIME_ERROR:
                error_message = "Runtime error occurred"
            elif result.category == ResponseCategory.TIMEOUT:
                error_message = "Execution timed out"
            elif result.category == ResponseCategory.SYSTEM_ERROR:
                error_message = "System error occurred"

            # Add stderr if available
            if result.stderr:
                if error_message:
                    error_message += f": {result.stderr}"
                else:
                    error_message = result.stderr

        return DeliberateCodeExecutionResponse(
            output=output,
            category=result.category,
            error_message=error_message,
            execution_time=result.execution_time
        )

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        # Return error response instead of raising
        return DeliberateCodeExecutionResponse(
            output="",
            category=ResponseCategory.SYSTEM_ERROR,
            error_message=f"Execution failed: {str(e)}",
            execution_time=0.0
        )

    finally:
        # Always release sandbox back to pool
        if sandbox:
            sandbox_manager.release_sandbox(language, sandbox)
            logger.info(f"Released sandbox for {language.value}")




