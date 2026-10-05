"""Synchronous deliberate code execution endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from web.api.deps import require_integration_token
from web.schemas.execution import (
    DeliberateCodeExecutionRequest,
    DeliberateCodeExecutionResponse,
    ExecutionErrorResponse,
)
from web.service.deliberate_execution_service import ExecutionServiceError, execute_code

router = APIRouter(prefix="/execute", tags=["Code Execution"])


@router.post(
    "",
    response_model=DeliberateCodeExecutionResponse,
    dependencies=[Depends(require_integration_token)],
    responses={
        401: {"description": "Missing or invalid integration token"},
        422: {"description": "Invalid or over-limit request"},
        503: {"model": ExecutionErrorResponse, "description": "Execution infrastructure unavailable"},
        504: {"model": ExecutionErrorResponse, "description": "Request deadline exceeded"},
    },
)
async def execute_code_endpoint(request: DeliberateCodeExecutionRequest):
    """Execute one command against sequential stdin cases, without grading.

    `test_cases` contains arrays of stdin lines. Omit it for one run with empty
    stdin. The command is parsed as executable and arguments; use an explicit
    `sh -c` command if shell operators are required.

    Example request:
    `{"language":"python","submission_files":[{"filename":"main.py",
    "content":"name = input()\\nprint('Hello, ' + name)"}],
    "program_command":"python main.py","test_cases":[["Alice"]]}`

    Example result:
    `{"results":[{"category":"success","stdout":"Hello, Alice\\n",
    "stderr":"","exit_code":0,"execution_time":0.01,"output":"Hello, Alice\\n",
    "error_message":null,"truncated":false}],"stopped_early":false}`
    """
    try:
        return await execute_code(request)
    except ExecutionServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
