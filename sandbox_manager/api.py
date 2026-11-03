"""Private sandbox control API.

Deployment boundary (see ``docs/contracts/SANDBOX.md``): a private network
reachable only by trusted grading hosts, one process with one worker, a shared
bearer token (``SANDBOX_API_TOKEN``) and a per-lease secret
(``X-Sandbox-Lease``) that binds every operation to the client that acquired it.
"""
import base64
import hmac
import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Callable, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, RuntimeUnavailableError, SandboxCapacityError, SandboxHandleError,
    SandboxInvalidatedError,
)
from sandbox_manager.handles import HandleRegistry
from sandbox_manager.models.api_models import (
    MAX_ARTIFACT_BYTES, AcquireSandboxResponse, DisposeSandboxResponse, ExtractedFileResponse,
    HttpResponseModel, InjectAssetsRequest, MakeRequestRequest, PrepareWorkdirRequest,
    ProcessRequestModel, ProcessResultModel,
)
from autograder.models.language import Language

logger = logging.getLogger(__name__)

LEASE_HEADER = "X-Sandbox-Lease"
DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


class BodyLimitMiddleware:
    """Reject request bodies above the configured limit, counted as received.

    The (bounded) body is buffered before the route runs, so an oversized
    stream is answered with 413 instead of a generic parsing error.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            return await self._reject(send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # client disconnected before sending the body
            body += message.get("body", b"")
            if len(body) > self.max_bytes:
                return await self._reject(send)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(send):
        response = JSONResponse(status_code=413, content={"detail": {
            "code": "request_too_large", "message": "Request body exceeds the control API limit"}})
        await response({"type": "http"}, None, send)


def _build_default_manager():
    from sandbox_manager.manager import SandboxManager
    from sandbox_manager.models.pool_config import SandboxPoolConfig
    configs = SandboxPoolConfig.load_from_yaml(os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml"))
    return SandboxManager(configs, lease_dir=os.getenv("SANDBOX_LEASE_DIR") or None)


def create_app(*, token: Optional[str] = None, manager_factory: Optional[Callable] = None,
               max_body_bytes: Optional[int] = None) -> FastAPI:
    """Build the control API. Configuration is read at startup, not import."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        secret = token if token is not None else os.getenv("SANDBOX_API_TOKEN", "")
        if not secret:
            raise RuntimeError("SANDBOX_API_TOKEN is required to start the sandbox control API")
        app.state.token = secret
        manager = (manager_factory or _build_default_manager)()
        manager.start()
        app.state.manager = manager
        app.state.handles = HandleRegistry(manager)
        try:
            yield
        finally:
            app.state.handles.close_all()
            manager.shutdown()

    app = FastAPI(title="Sandbox Manager API", version="2.0.0", lifespan=lifespan,
                  description="Private sandbox control API for trusted grading hosts")
    limit = max_body_bytes or int(os.getenv("SANDBOX_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES)))
    app.add_middleware(BodyLimitMiddleware, max_bytes=limit)

    def authenticate(request: Request, authorization: str = Header(default="")) -> None:
        expected = f"Bearer {request.app.state.token}"
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise _error(status.HTTP_401_UNAUTHORIZED, "unauthorized", "A valid control API token is required")

    def lease(x_sandbox_lease: str = Header(default="")) -> str:
        if len(x_sandbox_lease) < 32:
            raise _error(status.HTTP_401_UNAUTHORIZED, "lease_required", f"{LEASE_HEADER} must carry the lease secret")
        return x_sandbox_lease

    @contextmanager
    def operation(name: str):
        """Map failures to distinct, stable error codes."""
        try:
            yield
        except HTTPException:
            raise
        except SandboxHandleError as exc:
            code = status.HTTP_410_GONE if exc.code == "sandbox_expired" else status.HTTP_404_NOT_FOUND
            raise _error(code, exc.code, str(exc)) from exc
        except SandboxInvalidatedError as exc:
            raise _error(status.HTTP_409_CONFLICT, "sandbox_invalidated", str(exc)) from exc
        except ArtifactReadError as exc:
            logger.exception("Sandbox operation %s failed", name)
            raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "artifact_read_failed",
                         "The artifact exists but could not be read back") from exc
        except FileNotFoundError as exc:
            raise _error(status.HTTP_404_NOT_FOUND, "artifact_not_found", str(exc)) from exc
        except ArtifactTooLargeError as exc:
            raise _error(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "artifact_too_large", str(exc)) from exc
        except RuntimeUnavailableError as exc:
            raise _error(status.HTTP_501_NOT_IMPLEMENTED, "runtime_unavailable", str(exc)) from exc
        except SandboxCapacityError as exc:
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "capacity_unavailable", str(exc)) from exc
        except ValueError as exc:
            raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_request", str(exc)) from exc
        except Exception as exc:
            logger.exception("Sandbox operation %s failed", name)
            raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "execution_failed",
                         f"The sandbox could not complete {name}") from exc

    def registry(request: Request) -> HandleRegistry:
        return request.app.state.handles

    def check_timeout(handles: HandleRegistry, sandbox, timeout: float) -> None:
        limit_seconds = handles.manager.lease_seconds(sandbox.language)
        if timeout > limit_seconds:
            raise _error(422, "invalid_request", f"timeout exceeds the {limit_seconds}s lease limit")

    authenticated = [Depends(authenticate)]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/sandboxes/{language}", response_model=AcquireSandboxResponse,
              status_code=status.HTTP_201_CREATED, dependencies=authenticated)
    def acquire_sandbox(language: Language, request: Request, secret: str = Depends(lease)):
        with operation("acquisition"):
            handle = registry(request).acquire(language, secret)
            return AcquireSandboxResponse(sandbox_id=handle.handle_id, language=language.value,
                                          lease_seconds=registry(request).manager.lease_seconds(language))

    @app.post("/sandboxes/{sandbox_id}/prepare", dependencies=authenticated)
    def prepare_workdir(sandbox_id: str, body: PrepareWorkdirRequest, request: Request,
                        secret: str = Depends(lease)):
        with operation("preparation"):
            sandbox = registry(request).sandbox(sandbox_id, secret)
            sandbox.prepare_workdir({name: SubmissionFile(filename=item.filename, content=item.content)
                                     for name, item in body.submission_files.items()})
            return {"status": "success"}

    @app.post("/sandboxes/{sandbox_id}/inject", dependencies=authenticated)
    def inject_assets(sandbox_id: str, body: InjectAssetsRequest, request: Request,
                      secret: str = Depends(lease)):
        with operation("fixture staging"):
            sandbox = registry(request).sandbox(sandbox_id, secret)
            sandbox.inject_assets([ResolvedAsset(target=item.target, content=base64.b64decode(item.content),
                                                 read_only=item.read_only) for item in body.resolved_assets])
            return {"status": "success"}

    @app.post("/sandboxes/{sandbox_id}/process", response_model=ProcessResultModel, dependencies=authenticated)
    def run_process(sandbox_id: str, body: ProcessRequestModel, request: Request, secret: str = Depends(lease)):
        """Run one process with the shared contract. Never replayed by clients."""
        with operation("process execution"):
            handles = registry(request)
            sandbox = handles.sandbox(sandbox_id, secret)
            process = body.to_request()
            check_timeout(handles, sandbox, process.timeout)
            return ProcessResultModel.from_result(sandbox.run_process(process))

    @app.get("/sandboxes/{sandbox_id}/files", response_model=ExtractedFileResponse, dependencies=authenticated)
    def extract_file(sandbox_id: str, path: str, request: Request, max_bytes: int = MAX_ARTIFACT_BYTES,
                     secret: str = Depends(lease)):
        with operation("artifact extraction"):
            sandbox = registry(request).sandbox(sandbox_id, secret)
            if not 0 < max_bytes <= MAX_ARTIFACT_BYTES:
                raise ValueError(f"max_bytes must be between 1 and {MAX_ARTIFACT_BYTES}")
            extracted = sandbox.extract_file(path=path, max_bytes=max_bytes)
            return ExtractedFileResponse(
                path=extracted.path, content_bytes=base64.b64encode(extracted.content_bytes).decode("ascii"),
                size=extracted.size, content_text=extracted.content_text, encoding=extracted.encoding)

    @app.post("/sandboxes/{sandbox_id}/request", response_model=HttpResponseModel, dependencies=authenticated)
    def make_request(sandbox_id: str, body: MakeRequestRequest, request: Request, secret: str = Depends(lease)):
        with operation("HTTP request"):
            sandbox = registry(request).sandbox(sandbox_id, secret)
            response = sandbox.make_request(method=body.method, endpoint=body.endpoint, **body.kwargs)
            return HttpResponseModel(status_code=response.status_code, text=response.text, headers=response.headers,
                                     content=base64.b64encode(response.content).decode("ascii"), ok=response.ok)

    @app.delete("/sandboxes/{sandbox_id}", response_model=DisposeSandboxResponse, dependencies=authenticated,
                responses={202: {"model": DisposeSandboxResponse}})
    def dispose_sandbox(sandbox_id: str, request: Request, secret: str = Depends(lease)):
        with operation("disposal"):
            state = registry(request).dispose(sandbox_id, secret)
        if state == "closing":
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"state": "closing"})
        return DisposeSandboxResponse(state=state)

    @app.get("/stats", dependencies=authenticated)
    def get_stats(request: Request):
        manager = request.app.state.manager
        return {"pools": manager.get_pool_stats(), "handles": registry(request).stats(),
                "cleanup_problems": manager.cleanup_problems()}

    return app


app = create_app()
