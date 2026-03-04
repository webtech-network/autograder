"""Deliberate Code Execution endpoints."""

from fastapi import APIRouter, HTTPException

from web.config.logging import get_logger
from web.schemas.execution import (
    DeliberateCodeExecutionRequest,
    DeliberateCodeExecutionResponse,
)
from web.service.deliberate_execution_service import execute_code


logger = get_logger(__name__)
router = APIRouter(prefix="/execute", tags=["Code Execution"])


@router.post("", response_model=DeliberateCodeExecutionResponse)
async def execute_code_endpoint(request: DeliberateCodeExecutionRequest):
    """
    Execute code in a sandbox without grading.

    This endpoint is stateless and does not store any data.
    It's designed for testing and debugging code before actual submission.

    **Use Cases:**
    - Students testing their code before submitting for grading
    - Quick debugging of code issues
    - Interactive code execution (with stdin inputs)

    **Request:**
    - `language`: Programming language (python, java, node, cpp)
    - `submission_files`: List of files with filename and content
    - `program_command`: Command to execute (e.g., "python main.py")
    - `inputs`: Optional list of inputs to provide to the program

    **Response:**
    - `output`: Combined stdout/stderr output
    - `category`: Execution result category (success, runtime_error, timeout, etc.)
    - `error_message`: Error details if execution failed
    - `execution_time`: Time taken to execute in seconds

    **Example:**
    ```json
    {
        "language": "python",
        "submission_files": [
            {
                "filename": "main.py",
                "content": "name = input('Enter name: ')\\nprint(f'Hello, {name}!')"
            }
        ],
        "program_command": "python main.py",
        "inputs": [["Alice"]]
    }
    ```
    """
    try:
        logger.info("Code execution request received for language: %s", request.language)
        result = await execute_code(request)
        logger.info("Code execution completed with category: %s", result.category)
        return result
    except ValueError as e:
        logger.warning("Invalid request: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Execution endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during code execution") from e

