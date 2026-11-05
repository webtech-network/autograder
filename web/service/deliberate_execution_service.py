"""Host-owned synchronous execution, independent of grading semantics."""

import asyncio
import logging
from time import monotonic

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.process import ProcessRequest, ProcessStatus, ResponseCategory, SandboxExhausted, lines_to_stdin
from autograder.models.language import Language
from sandbox_manager.errors import SandboxCapacityTimeout
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
# The shared sandbox budget stayed full for the whole capacity wait; retry later.
BUSY = ("EXECUTION_BUSY", "All execution sandboxes are busy; retry later.", 503)


TIMEOUT_EXIT_CODE = 124  # the wire needs an integer for a stopped process; `category` is authoritative
EXHAUSTED_EXIT_CODE = 137  # SIGKILL: the program was stopped at the sandbox's memory or process limit
EXHAUSTED_MESSAGE = "Runtime error occurred: memory or process limit exceeded"


def _result(process) -> DeliberateCodeExecutionResult:
    """Map a process result to the wire. Output is already bounded by the host."""
    if process.status is ProcessStatus.NOT_STARTED:
        # The program could not be started: a service-side failure, as before.
        raise ExecutionServiceError(*UNAVAILABLE)
    labels = {
        ResponseCategory.RUNTIME_ERROR: "Runtime error occurred",
        ResponseCategory.TIMEOUT: "Execution timed out",
    }
    category = process.category
    error_message = labels.get(category)
    if error_message and process.stderr:
        error_message = f"{error_message}: {process.stderr}"
    return DeliberateCodeExecutionResult(
        category=category,
        stdout=process.stdout,
        stderr=process.stderr,
        exit_code=TIMEOUT_EXIT_CODE if process.status is ProcessStatus.TIMED_OUT else process.exit_code,
        execution_time=process.duration,
        output="\n".join(part for part in (process.stdout, process.stderr) if part),
        error_message=error_message,
        truncated=process.truncated,
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
        try:
            sandbox = capabilities.execution(language)
        except SandboxCapacityTimeout as exc:
            raise ExecutionServiceError(*BUSY) from exc
        if monotonic() >= deadline_at:
            raise ExecutionServiceError(*DEADLINE)
        files = {
            item.filename: SubmissionFile(filename=item.filename, content=item.content)
            for item in request.submission_files
        }
        sandbox.prepare_workdir(files)
        if request.assets:
            if capabilities.fixtures is None:
                raise ExecutionServiceError(*UNAVAILABLE)
            # Retrieval is by logical reference only; placement stays with the session.
            resolved = [ResolvedAsset(target=asset.target, content=capabilities.fixtures(asset.source),
                                      read_only=asset.read_only) for asset in request.assets]
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
            # The same process primitive as grading: argv, exact stdin bytes (each
            # line newline-terminated; an omitted or empty case is empty stdin).
            try:
                process = sandbox.run_process(ProcessRequest.command(
                    request.program_command, stdin=lines_to_stdin(case), timeout=timeout,
                    max_output_bytes=MAX_OUTPUT_BYTES))
            except SandboxExhausted:
                # The program's own result; nothing more can run in this sandbox.
                results.append(DeliberateCodeExecutionResult(
                    category=ResponseCategory.RUNTIME_ERROR, stdout="", stderr="", exit_code=EXHAUSTED_EXIT_CODE,
                    execution_time=0.0, output="", error_message=EXHAUSTED_MESSAGE, truncated=False))
                break
            results.append(_result(process))
            if process.status is ProcessStatus.TIMED_OUT:
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
