from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from sandbox_manager.models.sandbox_models import ResponseCategory, Language

class AcquireSandboxRequest(BaseModel):
    language: Language

class AcquireSandboxResponse(BaseModel):
    sandbox_id: str

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
    command: str
    timeout: int = 30
    workdir: str = "/app"

class RunBatchRequest(BaseModel):
    commands: List[str]
    program_command: Optional[str] = None
    timeout: int = 30
    workdir: str = "/app"

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
