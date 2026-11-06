"""Wire models and limits of the private sandbox control API.

Limits agree with the operations behind them:

* submissions use the shared host limits from ``sandbox_manager.submission_contract``;
* fixtures are bounded by the sandbox ``/tmp`` tmpfs size;
* a process request is the shared ``autograder.models.process`` contract
  (stdin is base64 on the wire and staged in chunks, so it is not limited by
  the kernel's per-argument size); its timeout is further bounded by the
  pool's ``running_timeout`` and each output stream by ``max_output_bytes``;
* artifact reads use the local ``extract_file`` default of 1 MiB;
* an acquisition waits for a slot of the host sandbox budget for at most
  :data:`MAX_ACQUIRE_WAIT_SECONDS`;
* the client's transport deadline for a process is its timeout plus
  :data:`TRANSPORT_MARGIN_SECONDS`.
"""
import base64
import binascii
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from autograder.models.process import (
    DEFAULT_MAX_OUTPUT_BYTES, DEFAULT_TIMEOUT_SECONDS, MAX_OUTPUT_BYTES, MAX_STDIN_BYTES, MAX_TIMEOUT_SECONDS,
    ProcessRequest, ProcessResult, ProcessStatus,
)
from sandbox_manager.docker_profile import FIXTURE_TMPFS_BYTES
from sandbox_manager.submission_contract import MAX_FILE_BYTES, MAX_FILES, MAX_PATH_BYTES, MAX_TOTAL_FILE_BYTES

MAX_FIXTURES = 100
MAX_FIXTURE_BYTES = FIXTURE_TMPFS_BYTES
MAX_ARTIFACT_BYTES = 1024 * 1024
# Base64 fixtures (4/3) plus JSON framing; larger bodies are rejected with 413.
MAX_BODY_BYTES = 48 * 1024 * 1024
TRANSPORT_MARGIN_SECONDS = 15
REQUEST_ID_PATTERN = r"^[A-Za-z0-9_-]{8,128}$"
MAX_ACQUIRE_WAIT_SECONDS = 900


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


class AcquireSandboxRequest(BaseModel):
    """``request_id`` makes acquisition replay-safe after a lost response.

    ``wait_seconds`` is how long the caller accepts to wait for a budget slot
    before ``503 CAPACITY_TIMEOUT``. ``lifetime_seconds`` is the sandbox's
    absolute lifetime from its grant; above the host's ``running_timeout`` it is
    refused with ``422 LIFETIME_EXCEEDED`` before any wait.
    """
    request_id: str = Field(pattern=REQUEST_ID_PATTERN)
    wait_seconds: float = Field(default=0.0, ge=0, le=MAX_ACQUIRE_WAIT_SECONDS)
    # The sandbox's absolute lifetime from its grant; omitted: the host's running_timeout.
    lifetime_seconds: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)


class AcquireSandboxResponse(BaseModel):
    sandbox_id: str
    request_id: str
    expires_in: int


class SubmissionFileModel(BaseModel):
    filename: str = Field(max_length=MAX_PATH_BYTES)
    content: str

    @field_validator("content")
    @classmethod
    def bounded_content(cls, value: str) -> str:
        if _utf8_size(value) > MAX_FILE_BYTES:
            raise ValueError(f"file content exceeds {MAX_FILE_BYTES} bytes")
        return value


class PrepareWorkdirRequest(BaseModel):
    submission_files: Dict[str, SubmissionFileModel] = Field(max_length=MAX_FILES)

    @field_validator("submission_files")
    @classmethod
    def bounded_total(cls, value):
        if sum(_utf8_size(item.content) for item in value.values()) > MAX_TOTAL_FILE_BYTES:
            raise ValueError(f"submission exceeds {MAX_TOTAL_FILE_BYTES} bytes")
        return value


class ResolvedAssetModel(BaseModel):
    target: str = Field(max_length=4096)
    content: str  # Base64 encoded string
    read_only: bool = True


class InjectAssetsRequest(BaseModel):
    resolved_assets: List[ResolvedAssetModel] = Field(max_length=MAX_FIXTURES)

    @field_validator("resolved_assets")
    @classmethod
    def bounded_total(cls, value):
        # Decoded size is at most 3/4 of the base64 length.
        if sum(len(item.content) * 3 // 4 for item in value) > MAX_FIXTURE_BYTES:
            raise ValueError(f"fixtures exceed {MAX_FIXTURE_BYTES} bytes")
        return value


class ProcessRequestModel(BaseModel):
    """Wire form of ``autograder.models.process.ProcessRequest`` (stdin is base64)."""
    model_config = ConfigDict(extra="forbid")
    argv: Optional[List[str]] = None
    shell: Optional[str] = None
    stdin: str = Field(default="", max_length=(MAX_STDIN_BYTES // 3 + 1) * 4)
    cwd: str = Field(default="/app", max_length=4096)
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS)
    max_output_bytes: int = Field(default=DEFAULT_MAX_OUTPUT_BYTES, ge=1, le=MAX_OUTPUT_BYTES)

    @classmethod
    def from_request(cls, request: ProcessRequest) -> "ProcessRequestModel":
        return cls(argv=list(request.argv) if request.argv is not None else None, shell=request.shell,
                   stdin=base64.b64encode(request.stdin).decode("ascii"), cwd=request.cwd,
                   timeout=request.timeout, max_output_bytes=request.max_output_bytes)

    def to_request(self) -> ProcessRequest:
        """Validate with the shared contract; raises ValueError for any violation."""
        try:
            stdin = base64.b64decode(self.stdin, validate=True)
        except binascii.Error as exc:
            raise ValueError("stdin must be base64") from exc
        return ProcessRequest(argv=tuple(self.argv) if self.argv is not None else None, shell=self.shell,
                              stdin=stdin, cwd=self.cwd, timeout=self.timeout,
                              max_output_bytes=self.max_output_bytes)


class ProcessResultModel(BaseModel):
    """Wire form of ``ProcessResult``; outputs are already bounded by the service."""
    status: Literal["exited", "timed_out", "not_started"]
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    duration: float = 0.0
    missing_executable: Optional[str] = None

    @classmethod
    def from_result(cls, result: ProcessResult) -> "ProcessResultModel":
        return cls(status=result.status.value, exit_code=result.exit_code, stdout=result.stdout,
                   stderr=result.stderr, stdout_truncated=result.stdout_truncated,
                   stderr_truncated=result.stderr_truncated, duration=result.duration,
                   missing_executable=result.missing_executable)

    def to_result(self) -> ProcessResult:
        return ProcessResult(ProcessStatus(self.status), self.exit_code, self.stdout, self.stderr,
                             self.stdout_truncated, self.stderr_truncated, self.duration, self.missing_executable)


class ExtractedFileResponse(BaseModel):
    path: str
    content_bytes: str  # Base64 encoded string
    size: int
    content_text: str = ""
    encoding: str = "utf-8"


class DisposeResponse(BaseModel):
    status: str  # A DisposalStatus value.
