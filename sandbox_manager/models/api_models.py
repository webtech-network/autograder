"""Wire models and limits of the private sandbox control API.

Limits agree with the operations behind them:

* submissions use the shared host limits from ``submission_contract``;
* fixtures are bounded by the sandbox ``/tmp`` tmpfs size;
* a batch's stdin is sent as one ``argv`` string, which Linux caps at 128 KiB;
* artifact reads use the local ``extract_file`` default of 1 MiB;
* command timeouts are bounded; the client's transport deadline is the command
  timeout plus :data:`TRANSPORT_MARGIN_SECONDS`.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from sandbox_manager.docker_profile import FIXTURE_TMPFS_BYTES
from sandbox_manager.models.sandbox_models import ResponseCategory
from submission_contract import MAX_FILE_BYTES, MAX_FILES, MAX_PATH_BYTES, MAX_TOTAL_FILE_BYTES

MAX_FIXTURES = 100
MAX_FIXTURE_BYTES = FIXTURE_TMPFS_BYTES
MAX_COMMAND_BYTES = 64 * 1024
MAX_BATCH_INPUT_BYTES = 96 * 1024
MAX_COMMAND_TIMEOUT_SECONDS = 300
MAX_OUTPUT_BYTES = 1024 * 1024          # Per stream; longer output is truncated.
MAX_ARTIFACT_BYTES = 1024 * 1024
# Base64 fixtures (4/3) plus JSON framing; larger bodies are rejected with 413.
MAX_BODY_BYTES = 48 * 1024 * 1024
TRANSPORT_MARGIN_SECONDS = 15
REQUEST_ID_PATTERN = r"^[A-Za-z0-9_-]{8,128}$"


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


class AcquireSandboxRequest(BaseModel):
    """``request_id`` makes acquisition replay-safe after a lost response."""
    request_id: str = Field(pattern=REQUEST_ID_PATTERN)


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


class RunCommandRequest(BaseModel):
    command: str = Field(min_length=1)
    timeout: int = Field(default=30, ge=1, le=MAX_COMMAND_TIMEOUT_SECONDS)
    workdir: str = Field(default="/app", max_length=4096)

    @field_validator("command")
    @classmethod
    def bounded_command(cls, value: str) -> str:
        if _utf8_size(value) > MAX_COMMAND_BYTES:
            raise ValueError(f"command exceeds {MAX_COMMAND_BYTES} bytes")
        return value


class RunBatchRequest(BaseModel):
    commands: List[str]
    program_command: Optional[str] = None
    timeout: int = Field(default=30, ge=1, le=MAX_COMMAND_TIMEOUT_SECONDS)
    workdir: str = Field(default="/app", max_length=4096)

    @field_validator("commands")
    @classmethod
    def bounded_input(cls, value: List[str]) -> List[str]:
        if _utf8_size("\n".join(value)) > MAX_BATCH_INPUT_BYTES:
            raise ValueError(f"batch input exceeds {MAX_BATCH_INPUT_BYTES} bytes")
        return value

    @field_validator("program_command")
    @classmethod
    def bounded_command(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and _utf8_size(value) > MAX_COMMAND_BYTES:
            raise ValueError(f"command exceeds {MAX_COMMAND_BYTES} bytes")
        return value


class CommandResponseModel(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    category: ResponseCategory
    truncated: bool = False


class ExtractedFileResponse(BaseModel):
    path: str
    content_bytes: str  # Base64 encoded string
    size: int
    content_text: str = ""
    encoding: str = "utf-8"


class DisposeResponse(BaseModel):
    status: str  # A DisposalStatus value.
