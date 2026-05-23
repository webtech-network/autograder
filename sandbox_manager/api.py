import base64
import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, status
import logging

from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.manager import (
    initialize_sandbox_manager,
    get_sandbox_manager
)
from sandbox_manager.models.pool_config import SandboxPoolConfig

logger = logging.getLogger(__name__)
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.models.api_models import (
    AcquireSandboxResponse,
    PrepareWorkdirRequest,
    InjectAssetsRequest,
    RunCommandRequest,
    RunBatchRequest,
    MakeRequestRequest,
    CommandResponseModel,
    ExtractedFileResponse,
    HttpResponseModel
)

# Global store for active sandboxes retrieved via the API
# mapping: sandbox_id -> SandboxContainer
active_sandboxes: Dict[str, SandboxContainer] = {}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load configuration and initialize sandbox manager
    config_file = os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml")
    pool_configs = SandboxPoolConfig.load_from_yaml(config_file)
    initialize_sandbox_manager(pool_configs)
    
    yield
    
    # Shutdown
    try:
        manager = get_sandbox_manager()
        manager.shutdown()
    except Exception:
        pass


app = FastAPI(
    title="Sandbox Manager API",
    description="REST API for managing Sandbox containers independently",
    version="1.0.0",
    lifespan=lifespan
)

def _get_sandbox_or_404(sandbox_id: str) -> SandboxContainer:
    sandbox = active_sandboxes.get(sandbox_id)
    if not sandbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    return sandbox


@app.post("/sandboxes/{language}", response_model=AcquireSandboxResponse)
def acquire_sandbox(language: Language):
    manager = get_sandbox_manager()
    try:
        sandbox = manager.get_sandbox(language)
        sandbox_id = sandbox.container_ref.id
        active_sandboxes[sandbox_id] = sandbox
        return AcquireSandboxResponse(sandbox_id=sandbox_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.post("/sandboxes/{sandbox_id}/prepare")
def prepare_workdir(sandbox_id: str, request: PrepareWorkdirRequest):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        submission_files = {
            name: SubmissionFile(filename=sf.filename, content=sf.content)
            for name, sf in request.submission_files.items()
        }
        sandbox.prepare_workdir(submission_files)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.post("/sandboxes/{sandbox_id}/inject")
def inject_assets(sandbox_id: str, request: InjectAssetsRequest):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        resolved_assets = [
            ResolvedAsset(
                target=asset.target,
                content=base64.b64decode(asset.content),
                read_only=asset.read_only
            )
            for asset in request.resolved_assets
        ]
        sandbox.inject_assets(resolved_assets)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.post("/sandboxes/{sandbox_id}/run", response_model=CommandResponseModel)
def run_command(sandbox_id: str, request: RunCommandRequest):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        response = sandbox.run_command(
            command=request.command,
            timeout=request.timeout,
            workdir=request.workdir
        )
        return CommandResponseModel(
            stdout=response.stdout,
            stderr=response.stderr,
            exit_code=response.exit_code,
            execution_time=response.execution_time,
            category=response.category
        )
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.post("/sandboxes/{sandbox_id}/run-batch", response_model=CommandResponseModel)
def run_batch(sandbox_id: str, request: RunBatchRequest):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        response = sandbox.run_commands(
            commands=request.commands,
            program_command=request.program_command,
            timeout=request.timeout,
            workdir=request.workdir
        )
        return CommandResponseModel(
            stdout=response.stdout,
            stderr=response.stderr,
            exit_code=response.exit_code,
            execution_time=response.execution_time,
            category=response.category
        )
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.get("/sandboxes/{sandbox_id}/files", response_model=ExtractedFileResponse)
def extract_file(sandbox_id: str, path: str, max_bytes: int = 1_048_576):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        extracted = sandbox.extract_file(path=path, max_bytes=max_bytes)
        return ExtractedFileResponse(
            path=extracted.path,
            content_bytes=base64.b64encode(extracted.content_bytes).decode('ascii'),
            size=extracted.size,
            content_text=extracted.content_text,
            encoding=extracted.encoding
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.post("/sandboxes/{sandbox_id}/request", response_model=HttpResponseModel)
def make_request(sandbox_id: str, request: MakeRequestRequest):
    sandbox = _get_sandbox_or_404(sandbox_id)
    try:
        http_response = sandbox.make_request(
            method=request.method,
            endpoint=request.endpoint,
            **request.kwargs
        )
        return HttpResponseModel(
            status_code=http_response.status_code,
            text=http_response.text,
            headers=http_response.headers,
            content=base64.b64encode(http_response.content).decode('ascii'),
            ok=http_response.ok
        )
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.delete("/sandboxes/{sandbox_id}")
def release_sandbox(sandbox_id: str):
    sandbox = active_sandboxes.pop(sandbox_id, None)
    if not sandbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    
    manager = get_sandbox_manager()
    try:
        manager.release_sandbox(sandbox.language, sandbox)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.delete("/sandboxes/{sandbox_id}/destroy")
def destroy_sandbox(sandbox_id: str):
    sandbox = active_sandboxes.pop(sandbox_id, None)
    if not sandbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")
    
    manager = get_sandbox_manager()
    try:
        manager.destroy_sandbox(sandbox.language, sandbox)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.get("/stats")
def get_stats():
    manager = get_sandbox_manager()
    return manager.get_pool_stats()
