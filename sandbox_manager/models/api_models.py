from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from sandbox_manager.models.sandbox_models import ResponseCategory

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_COMMAND_CHARS = 64 * 1024
MAX_COMMAND_TIMEOUT_SECONDS = 600  # further bounded by the pool's lease duration


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


class RunCommandRequest(BaseModel):
    command: str = Field(max_length=MAX_COMMAND_CHARS)
    timeout: int = Field(default=30, ge=1, le=MAX_COMMAND_TIMEOUT_SECONDS)
    workdir: str = Field(default="/app", max_length=4096)


class RunBatchRequest(BaseModel):
    commands: List[str]
    program_command: Optional[str] = Field(default=None, max_length=MAX_COMMAND_CHARS)
    timeout: int = Field(default=30, ge=1, le=MAX_COMMAND_TIMEOUT_SECONDS)
    workdir: str = Field(default="/app", max_length=4096)


class MakeRequestRequest(BaseModel):
    method: str
    endpoint: str
    kwargs: dict = Field(default_factory=dict)


class CommandResponseModel(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    category: ResponseCategory

    @classmethod
    def from_response(cls, response) -> "CommandResponseModel":
        return cls(stdout=response.stdout, stderr=response.stderr, exit_code=response.exit_code,
                   execution_time=response.execution_time, category=response.category)


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
