"""Host-owned synchronous execution, independent of grading semantics."""

import asyncio
import logging
from time import monotonic

from autograder.models.dataclass.submission import SubmissionFile
from execution_host.assets.resolver import AssetSourceResolver
from sandbox_manager.models.sandbox_models import Language, ResponseCategory
from web.schemas.execution import (
    CASE_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TOTAL_FILE_BYTES,
    REQUEST_DEADLINE_SECONDS,
    DeliberateCodeExecutionRequest,
    DeliberateCodeExecutionResponse,
    DeliberateCodeExecutionResult,
)

logger = logging.getLogger(__name__)


class ExecutionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


UNAVAILABLE = ("EXECUTION_UNAVAILABLE", "Execution service is unavailable.", 503)
DEADLINE = ("EXECUTION_DEADLINE_EXCEEDED", "Execution deadline exceeded.", 504)


def _bounded(text: str) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text, False
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore"), True


def _result(command_result) -> DeliberateCodeExecutionResult:
    if command_result.category == ResponseCategory.SYSTEM_ERROR:
        raise ExecutionServiceError(*UNAVAILABLE)
    stdout, out_cut = _bounded(command_result.stdout)
    stderr, err_cut = _bounded(command_result.stderr)
    labels = {
        ResponseCategory.RUNTIME_ERROR: "Runtime error occurred",
        ResponseCategory.COMPILATION_ERROR: "Compilation failed",
        ResponseCategory.TIMEOUT: "Execution timed out",
    }
    error_message = labels.get(command_result.category)
    if error_message and stderr:
        error_message = f"{error_message}: {stderr}"
    return DeliberateCodeExecutionResult(
        category=command_result.category,
        stdout=stdout,
        stderr=stderr,
        exit_code=command_result.exit_code,
        execution_time=command_result.execution_time,
        output="\n".join(part for part in (stdout, stderr) if part),
        error_message=error_message,
        truncated=out_cut or err_cut,
    )


def _execute_in_worker(request: DeliberateCodeExecutionRequest, deadline_at: float, capabilities):
    """Keep acquisition, execution, and cleanup in one worker even after disconnect."""
    if monotonic() >= deadline_at:
        raise ExecutionServiceError(*DEADLINE)
    if capabilities is None or capabilities.execution is None:
        raise ExecutionServiceError(*UNAVAILABLE)

    language = Language(request.language)
    sandbox = None
    try:
        sandbox = capabilities.execution(language)
        if monotonic() >= deadline_at:
            raise ExecutionServiceError(*DEADLINE)
        files = {
            item.filename: SubmissionFile(filename=item.filename, content=item.content)
            for item in request.submission_files
        }
        sandbox.prepare_workdir(files)
        if request.assets:
            resolved = AssetSourceResolver().resolve_assets(request.assets)
            if sum(len(item.content) for item in resolved) > MAX_TOTAL_FILE_BYTES:
                raise ExecutionServiceError(*UNAVAILABLE)
            sandbox.inject_assets(resolved)

        results = []
        cases = request.test_cases if request.test_cases is not None else [[]]
        for case in cases:
            remaining = deadline_at - monotonic()
            if remaining <= 0:
                raise ExecutionServiceError(*DEADLINE)
            timeout = max(1, min(CASE_TIMEOUT_SECONDS, int(remaining)))
            if case:
                command_result = sandbox.run_commands(
                    case, program_command=request.program_command, timeout=timeout, workdir="/app"
                )
            else:
                command_result = sandbox.run_command(
                    request.program_command, timeout=timeout, workdir="/app"
                )
            results.append(_result(command_result))
            if command_result.category == ResponseCategory.TIMEOUT:
                break
        return DeliberateCodeExecutionResponse(
            results=results, stopped_early=len(results) < len(cases)
        )
    except ExecutionServiceError:
        raise
    except Exception as exc:
        logger.exception("Deliberate execution infrastructure failed")
        raise ExecutionServiceError(*UNAVAILABLE) from exc
    finally:
        if sandbox is not None:
            try:
                sandbox.close()
            except Exception:
                # A known process result remains valid even if disposal fails.
                logger.exception("Deliberate execution session cleanup failed")


def _observe_worker(task: asyncio.Task) -> None:
    """Consume a detached worker's error after response deadline or disconnect."""
    if not task.cancelled():
        try:
            task.result()
        except Exception:
            logger.exception("Detached deliberate execution finished with an error")


async def execute_code(request: DeliberateCodeExecutionRequest, *, capabilities=None, tasks=None) -> DeliberateCodeExecutionResponse:
    deadline_at = monotonic() + REQUEST_DEADLINE_SECONDS
    worker = asyncio.create_task(asyncio.to_thread(_execute_in_worker, request, deadline_at, capabilities))
    if tasks is not None:
        tasks.add(worker)
        worker.add_done_callback(tasks.discard)
    try:
        return await asyncio.wait_for(
            asyncio.shield(worker), timeout=REQUEST_DEADLINE_SECONDS
        )
    except asyncio.TimeoutError as exc:
        # The worker retains its pool slot and releases the sandbox in its finally block.
        worker.add_done_callback(_observe_worker)
        raise ExecutionServiceError(*DEADLINE) from exc
    except asyncio.CancelledError:
        worker.add_done_callback(_observe_worker)
        raise
