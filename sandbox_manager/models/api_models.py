import base64
import binascii
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from autograder.models.process import (
    DEFAULT_MAX_OUTPUT_BYTES, DEFAULT_TIMEOUT_SECONDS, MAX_OUTPUT_BYTES, MAX_STDIN_BYTES, MAX_TIMEOUT_SECONDS,
    ProcessRequest, ProcessResult, ProcessStatus,
)

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


class AcquireSandboxResponse(BaseModel):
    sandbox_id: str
    language: str
    lease_seconds: int


class DisposeSandboxResponse(BaseModel):
    state: str  # "disposed" (200) or "closing" (202, retained and retried by the service)


class SubmissionFileModel(BaseModel):
    filename: str
    content: str


class PrepareWorkdirRequest(BaseModel):
    submission_files: Dict[str, SubmissionFileModel]


class ResolvedAssetModel(BaseModel):
    target: str
    content: str  # Base64 encoded string
    read_only: bool = True


class InjectAssetsRequest(BaseModel):
    resolved_assets: List[ResolvedAssetModel]


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


class MakeRequestRequest(BaseModel):
    method: str
    endpoint: str
    kwargs: dict = Field(default_factory=dict)


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


class HttpResponseModel(BaseModel):
    status_code: int
    text: str
    headers: Dict[str, str]
    content: str  # Base64 encoded string
    ok: bool
