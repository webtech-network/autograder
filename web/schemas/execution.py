"""Bounded, synchronous deliberate execution wire contract."""

import posixpath
import shlex

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from sandbox_manager.models.sandbox_models import Language, ResponseCategory


MAX_FILES = 20
MAX_FILE_BYTES = 64 * 1024
MAX_TOTAL_FILE_BYTES = 256 * 1024
MAX_ASSETS = 5
MAX_CASES = 4
MAX_STDIN_BYTES = 16 * 1024
MAX_OUTPUT_BYTES = 16 * 1024  # Per stream, per case, on the wire.
CASE_TIMEOUT_SECONDS = 8
REQUEST_DEADLINE_SECONDS = 45


class ExecutionFile(BaseModel):
    """One UTF-8 source file staged under the sandbox work directory."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255, strict=True)
    content: str = Field(strict=True)

    @field_validator("filename")
    @classmethod
    def relative_filename(cls, value: str) -> str:
        """Require an unambiguous path within the work directory."""
        normalized = posixpath.normpath(value)
        if normalized != value or normalized in (".", "..") or normalized.startswith(("/", "../")):
            raise ValueError("filename must be a normalized relative path")
        if "\\" in value or "\x00" in value:
            raise ValueError("filename must be a normalized relative path")
        return value

    @field_validator("content")
    @classmethod
    def bounded_content(cls, value: str) -> str:
        """Bound the encoded file content before creating a sandbox."""
        if len(value.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("file content exceeds 64 KiB")
        return value


class ExecutionAsset(BaseModel):
    """An asset reference supplied by an authenticated host."""

    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=255, strict=True)
    target: str = Field(min_length=1, max_length=255, strict=True)
    read_only: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def valid_paths(self):
        """Keep asset references relative and targets under /tmp."""
        source = posixpath.normpath(self.source)
        target = posixpath.normpath(self.target)
        if source != self.source or source in (".", "..") or source.startswith(("/", "../")):
            raise ValueError("asset source must be a normalized relative path")
        if "\\" in self.source or "\x00" in self.source:
            raise ValueError("asset source must be a normalized relative path")
        if (target != self.target or not target.startswith("/tmp/")
                or "\\" in self.target or "\x00" in self.target):
            raise ValueError("asset target must be a normalized path under /tmp")
        return self


class DeliberateCodeExecutionRequest(BaseModel):
    """Run one command against at most four sequential stdin cases."""

    model_config = ConfigDict(extra="forbid")
    language: str = Field(strict=True)
    submission_files: list[ExecutionFile] = Field(min_length=1, max_length=MAX_FILES)
    program_command: str = Field(min_length=1, max_length=256, strict=True)
    test_cases: list[list[StrictStr]] | None = Field(default=None, max_length=MAX_CASES)
    assets: list[ExecutionAsset] = Field(default_factory=list, max_length=MAX_ASSETS)

    @field_validator("language")
    @classmethod
    def canonical_language(cls, value: str) -> str:
        """Accept only sandbox language identifiers exposed by this host."""
        if value not in {language.value for language in Language}:
            raise ValueError("language must be a supported lowercase identifier")
        return value

    @field_validator("program_command")
    @classmethod
    def executable_command(cls, value: str) -> str:
        """Require a parseable executable and argument string."""
        if "\x00" in value or not value.strip():
            raise ValueError("program_command must be nonempty")
        try:
            if not shlex.split(value):
                raise ValueError("program_command must contain an executable")
        except ValueError as exc:
            raise ValueError("program_command must be valid shell-style argument quoting") from exc
        return value

    @model_validator(mode="after")
    def bounded_request(self):
        """Apply limits involving more than one request field."""
        names = [item.filename for item in self.submission_files]
        if len(names) != len(set(names)):
            raise ValueError("submission_files contains duplicate filenames")
        if sum(len(item.content.encode("utf-8")) for item in self.submission_files) > MAX_TOTAL_FILE_BYTES:
            raise ValueError("submission_files exceeds 256 KiB total")
        if self.test_cases == []:
            raise ValueError("test_cases must be omitted or contain at least one case")
        for case in self.test_cases or []:
            if len("\n".join(case).encode("utf-8")) > MAX_STDIN_BYTES:
                raise ValueError("stdin case exceeds 16 KiB")
        return self


class DeliberateCodeExecutionResult(BaseModel):
    """Student process outcome. Infrastructure errors use non-200 HTTP responses."""

    category: ResponseCategory
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    output: str  # Display field; stdout followed by stderr.
    error_message: str | None = None
    truncated: bool = False


class DeliberateCodeExecutionResponse(BaseModel):
    """Ordered process results, possibly a prefix after a timeout."""

    results: list[DeliberateCodeExecutionResult]
    stopped_early: bool = False  # A timeout ends the batch; results are a prefix.


class ExecutionError(BaseModel):
    """Safe machine-readable service failure."""

    code: str
    message: str


class ExecutionErrorResponse(BaseModel):
    """HTTP error envelope for service failures."""

    detail: ExecutionError
