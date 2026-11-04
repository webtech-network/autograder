"""Private sandbox control API.

Deployment boundary: this service is reachable only from trusted hosts on a
private network (Compose ``expose``, never a published port) and every route
except ``GET /health`` requires ``Authorization: Bearer $SANDBOX_API_TOKEN``.
The service refuses to start without a token unless
``SANDBOX_API_ALLOW_UNAUTHENTICATED=true`` is set for local development.

Worker model: handles live in this process's memory. Run exactly one worker
process (``uvicorn --workers 1``); the service refuses ``WEB_CONCURRENCY`` > 1.
Handles are random and expire after an idle TTL; a reaper disposes expired
handles. Each handle holds one slot of the manager's sandbox budget, which
bounds them. Acquisition waits for a slot in its own threads (never in the
threads other routes need to free slots) and is replay-safe through a client
request id. ``DELETE`` marks a handle closing, disposes it, and only then forgets it,
remembering it in a bounded tombstone so a repeated ``DELETE`` succeeds.
"""
import base64
import hmac
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import anyio
from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.process import SandboxExhausted
from sandbox_manager.errors import (
    ArtifactReadError,
    ArtifactTooLargeError,
    RuntimeUnavailableError,
    SandboxCapacityTimeout,
    SandboxInvalidatedError,
)
from sandbox_manager.language_pool import SandboxUnavailableError
from sandbox_manager.models.api_models import (
    MAX_ARTIFACT_BYTES,
    MAX_BODY_BYTES,
    AcquireSandboxRequest,
    AcquireSandboxResponse,
    DisposeResponse,
    ExtractedFileResponse,
    InjectAssetsRequest,
    PrepareWorkdirRequest,
    ProcessRequestModel,
    ProcessResultModel,
)
from sandbox_manager.models.sandbox_models import DisposalStatus, SandboxState
from autograder.models.language import Language

logger = logging.getLogger(__name__)

TRUE_VALUES = {"1", "true", "yes"}
# Threads in which acquisitions wait for a budget slot. Separate from the route
# threadpool, so waiting acquisitions can never starve the DELETE that frees a slot.
ACQUIRE_THREADS = 256


@dataclass(frozen=True)
class ControlSettings:
    """Startup policy of the control service, read from the environment."""
    token: Optional[str] = field(default=None, repr=False)
    allow_unauthenticated: bool = False
    handle_ttl_seconds: float = 600.0          # Idle time before a handle expires.
    tombstone_seconds: float = 3600.0          # How long closed handles are remembered.
    max_tombstones: int = 10_000
    reaper_interval_seconds: float = 5.0
    worker_count: int = 1

    @classmethod
    def from_env(cls) -> "ControlSettings":
        if os.getenv("SANDBOX_MAX_HANDLES") is not None:
            raise RuntimeError("SANDBOX_MAX_HANDLES was removed: open handles are bounded by the host sandbox "
                               "budget (general.max_sandboxes in sandbox_config.yml). Unset it.")
        return cls(
            token=os.getenv("SANDBOX_API_TOKEN") or None,
            allow_unauthenticated=os.getenv("SANDBOX_API_ALLOW_UNAUTHENTICATED", "").lower() in TRUE_VALUES,
            handle_ttl_seconds=float(os.getenv("SANDBOX_HANDLE_TTL_SECONDS", "600")),
            tombstone_seconds=float(os.getenv("SANDBOX_HANDLE_TOMBSTONE_SECONDS", "3600")),
            worker_count=int(os.getenv("WEB_CONCURRENCY", "1")),
        )

    def validate(self) -> None:
        if self.worker_count != 1:
            raise RuntimeError("The sandbox control API keeps handles in process memory; "
                               "run exactly one worker (WEB_CONCURRENCY=1).")
        if self.token is None and not self.allow_unauthenticated:
            raise RuntimeError("SANDBOX_API_TOKEN is required. For local development only, set "
                               "SANDBOX_API_ALLOW_UNAUTHENTICATED=true.")
        if self.token is None:
            logger.warning("!!! SANDBOX CONTROL API IS UNAUTHENTICATED (SANDBOX_API_ALLOW_UNAUTHENTICATED=true). "
                           "Any client that reaches this port can run code and control sandboxes. "
                           "Never use this outside local development. !!!")
        if self.handle_ttl_seconds <= 0 or self.tombstone_seconds <= 0:
            raise RuntimeError("Handle lifetimes must be positive")


class ControlError(Exception):
    """A safe, coded API error."""
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _handle_not_found():
    return ControlError(status.HTTP_404_NOT_FOUND, "HANDLE_NOT_FOUND", "Sandbox handle is unknown.")


@dataclass(eq=False)
class Handle:
    handle_id: str
    request_id: str
    language: Language
    sandbox: object
    last_used: float
    state: str = "active"      # active -> closing -> forgotten (tombstoned)
    in_flight: int = 0
    disposing: bool = False


class HandleRegistry:
    """In-memory, expiring handles for one worker process, bounded by the sandbox budget."""

    def __init__(self, manager, *, ttl: float, tombstone_ttl: float = 3600.0,
                 max_tombstones: int = 10_000, clock: Callable[[], float] = time.monotonic):
        self.manager = manager
        self.ttl = ttl
        self.tombstone_ttl = tombstone_ttl
        self.max_tombstones = max_tombstones
        self.clock = clock
        self._lock = threading.Lock()
        self._handles: Dict[str, Handle] = {}
        self._by_request: Dict[str, str] = {}
        # request_id -> (language, done) while that acquisition is waiting or creating.
        self._pending: Dict[str, tuple] = {}
        # handle_id -> (reason, forgotten_at, request_id, language)
        self._tombstones: "OrderedDict[str, tuple]" = OrderedDict()

    # -------------------------------------------------------------- bookkeeping
    def _prune_tombstones(self, now: float) -> None:
        while self._tombstones:
            handle_id, (_, at, request_id, _) = next(iter(self._tombstones.items()))
            if len(self._tombstones) <= self.max_tombstones and now - at <= self.tombstone_ttl:
                break
            self._tombstones.popitem(last=False)
            if self._by_request.get(request_id) == handle_id:
                del self._by_request[request_id]

    def _forget(self, handle: Handle, reason: str) -> None:
        if self._handles.pop(handle.handle_id, None) is not None:
            self._tombstones[handle.handle_id] = (reason, self.clock(), handle.request_id, handle.language)
            self._prune_tombstones(self.clock())

    def _gone_error(self, handle_id: str) -> ControlError:
        reason = self._tombstones[handle_id][0]
        if reason == "expired":
            return ControlError(status.HTTP_410_GONE, "HANDLE_EXPIRED", "Sandbox handle expired and was disposed.")
        return ControlError(status.HTTP_410_GONE, "HANDLE_CLOSED", "Sandbox handle was closed.")

    def stats(self) -> dict:
        with self._lock:
            return {"handles": len(self._handles), "acquiring": len(self._pending),
                    "closing": sum(1 for h in self._handles.values() if h.state == "closing"),
                    "tombstones": len(self._tombstones)}

    # -------------------------------------------------------------- operations
    def acquire(self, language: Language, request_id: str, wait_seconds: float = 0.0) -> Handle:
        """Hand out a new handle, or the existing one for a replayed ``request_id``.

        Acquisitions run concurrently; a replay of one still in progress waits
        for it instead of creating a second container.
        """
        while True:
            with self._lock:
                self._prune_tombstones(self.clock())
                existing = self._by_request.get(request_id)
                pending = self._pending.get(request_id)
                if existing is not None:
                    handle = self._handles.get(existing)
                    language_of = handle.language if handle else self._tombstones[existing][3]
                elif pending is not None:
                    language_of = pending[0]
                else:
                    done = threading.Event()
                    self._pending[request_id] = (language, done)
                    break
                if language_of != language:
                    raise ControlError(status.HTTP_409_CONFLICT, "REQUEST_ID_CONFLICT",
                                       "Request id was used for another acquisition.")
                if existing is not None:
                    if handle is None:
                        raise self._gone_error(existing)
                    handle.last_used = self.clock()
                    return handle  # Replay after a lost response: same handle, no second container.
            pending[1].wait()  # The original attempt ends within its own wait; then look again.
        try:
            try:
                sandbox = self.manager.get_sandbox(language, wait_seconds=wait_seconds)
            except SandboxCapacityTimeout as exc:
                raise ControlError(status.HTTP_503_SERVICE_UNAVAILABLE, "CAPACITY_TIMEOUT",
                                   "No sandbox slot became free within the requested wait.") from exc
            except SandboxUnavailableError as exc:
                raise ControlError(status.HTTP_503_SERVICE_UNAVAILABLE, "SANDBOX_UNAVAILABLE",
                                   "No sandbox is available now.") from exc
            except RuntimeUnavailableError as exc:
                # A permanent host gap, distinct from transient capacity (503).
                raise ControlError(status.HTTP_501_NOT_IMPLEMENTED, "RUNTIME_UNAVAILABLE",
                                   "This host has no runtime for the language.") from exc
            handle = Handle(secrets.token_urlsafe(32), request_id, language, sandbox, self.clock())
            with self._lock:
                self._handles[handle.handle_id] = handle
                self._by_request[request_id] = handle.handle_id
            return handle
        finally:
            with self._lock:
                del self._pending[request_id]
            done.set()

    @contextmanager
    def use(self, handle_id: str):
        """Borrow an active handle for one operation; the reaper never expires it meanwhile."""
        with self._lock:
            handle = self._handles.get(handle_id)
            if handle is None:
                if handle_id in self._tombstones:
                    raise self._gone_error(handle_id)
                raise _handle_not_found()
            if handle.state != "active":
                raise ControlError(status.HTTP_410_GONE, "HANDLE_CLOSED", "Sandbox handle is closing.")
            if getattr(handle.sandbox, "state", SandboxState.ACTIVE) is not SandboxState.ACTIVE:
                # The pool disposed it (running timeout); the reaper will tombstone it.
                raise ControlError(status.HTTP_410_GONE, "HANDLE_EXPIRED",
                                   "Sandbox exceeded its running timeout and was disposed.")
            handle.in_flight += 1
        try:
            yield handle
        finally:
            with self._lock:
                handle.in_flight -= 1
                handle.last_used = self.clock()

    def close(self, handle_id: str) -> str:
        """Dispose and forget a handle. Repeated calls for a remembered handle succeed."""
        with self._lock:
            handle = self._handles.get(handle_id)
            if handle is None:
                if handle_id in self._tombstones:
                    return DisposalStatus.ALREADY_DISPOSED.value
                raise _handle_not_found()
            handle.state = "closing"
            if handle.disposing:
                return DisposalStatus.CLOSING.value
            handle.disposing = True
        return self._dispose(handle, "closed")

    def _dispose(self, handle: Handle, reason: str) -> str:
        try:
            result = self.manager.dispose(handle.sandbox)
        except Exception as exc:
            # The closing record stays; a repeated DELETE or the reaper retries.
            logger.exception("Disposal of handle failed; it remains closing for retry")
            with self._lock:
                handle.disposing = False
            raise ControlError(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPOSAL_FAILED",
                               "Sandbox disposal failed; retry the request.") from exc
        with self._lock:
            handle.disposing = False
            if result is not DisposalStatus.CLOSING:
                # DISPOSED / ALREADY_DISPOSED, or QUARANTINED: the pool now owns
                # the retry record and reports it in its stats.
                self._forget(handle, reason)
        return result.value

    def reap(self) -> int:
        """Dispose handles idle beyond the TTL or whose sandbox the pool already disposed."""
        now = self.clock()
        with self._lock:
            self._prune_tombstones(now)
            due = []
            for handle in self._handles.values():
                if handle.disposing or handle.in_flight:
                    continue
                pool_disposed = getattr(handle.sandbox, "state", SandboxState.ACTIVE) is not SandboxState.ACTIVE
                if handle.state == "closing" or pool_disposed or now - handle.last_used > self.ttl:
                    handle.state = "closing"
                    handle.disposing = True
                    due.append(handle)
        for handle in due:
            logger.warning("Expiring sandbox handle %s… (%s)", handle.handle_id[:6], handle.language.value)
            try:
                self._dispose(handle, "expired")
            except ControlError:
                pass  # Logged; retried on the next pass.
        return len(due)

    def run_reaper(self, stop: threading.Event, interval: float) -> None:
        while not stop.wait(interval):
            try:
                self.reap()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Sandbox handle reaper failed")

    def forget_all(self) -> None:
        with self._lock:
            for handle in list(self._handles.values()):
                self._forget(handle, "closed")


# ---------------------------------------------------------------------- HTTP

class BodyLimitMiddleware:
    """Reject request bodies above the control API limit before parsing."""
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > self.max_bytes:
            return await _error_response(413, "REQUEST_TOO_LARGE", "Request body is too large.")(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise ControlError(413, "REQUEST_TOO_LARGE", "Request body is too large.")
            return message

        try:
            return await self.app(scope, bounded_receive, send)
        except ControlError as exc:
            return await _error_response(exc.status_code, exc.code, exc.message)(scope, receive, send)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message}},
                        headers=headers)


def require_token(request: Request) -> None:
    token = request.app.state.control.token
    if token is None:
        return
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip().encode(), token.encode()):
        raise ControlError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "A valid bearer token is required.")


def _registry(request: Request) -> HandleRegistry:
    return request.app.state.registry


def _sandbox_error(exc: Exception) -> ControlError:
    if isinstance(exc, SandboxExhausted):
        # The submission's own result: nothing more can run; only DELETE remains useful.
        return ControlError(status.HTTP_409_CONFLICT, "SANDBOX_EXHAUSTED",
                            "The submission exhausted the sandbox's memory or process limit.")
    if isinstance(exc, SandboxInvalidatedError):
        # The sandbox cannot be trusted any more; only DELETE remains useful.
        return ControlError(status.HTTP_409_CONFLICT, "SANDBOX_INVALIDATED",
                            "The sandbox was invalidated; dispose it.")
    logger.error("Sandbox operation failed: %s", exc, exc_info=True)
    return ControlError(status.HTTP_500_INTERNAL_SERVER_ERROR, "SANDBOX_ERROR", "The sandbox operation failed.")


router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/sandboxes/{language}", response_model=AcquireSandboxResponse)
async def acquire_sandbox(language: Language, body: AcquireSandboxRequest, request: Request):
    registry = _registry(request)
    handle = await anyio.to_thread.run_sync(registry.acquire, language, body.request_id, body.wait_seconds,
                                            limiter=request.app.state.acquire_limiter)
    return AcquireSandboxResponse(sandbox_id=handle.handle_id, request_id=handle.request_id,
                                  expires_in=int(registry.ttl))


@router.post("/sandboxes/{sandbox_id}/prepare")
def prepare_workdir(sandbox_id: str, body: PrepareWorkdirRequest, request: Request):
    with _registry(request).use(sandbox_id) as handle:
        files = {name: SubmissionFile(filename=item.filename, content=item.content)
                 for name, item in body.submission_files.items()}
        try:
            handle.sandbox.prepare_workdir(files)
        except Exception as exc:
            raise _sandbox_error(exc) from exc
    return {"status": "success"}


@router.post("/sandboxes/{sandbox_id}/inject")
def inject_assets(sandbox_id: str, body: InjectAssetsRequest, request: Request):
    with _registry(request).use(sandbox_id) as handle:
        try:
            assets = [ResolvedAsset(target=item.target, content=base64.b64decode(item.content, validate=True),
                                    read_only=item.read_only) for item in body.resolved_assets]
        except ValueError as exc:
            raise ControlError(422, "INVALID_REQUEST", "Fixture content must be base64.") from exc
        try:
            handle.sandbox.inject_assets(assets)
        except Exception as exc:
            raise _sandbox_error(exc) from exc
    return {"status": "success"}


@router.post("/sandboxes/{sandbox_id}/process", response_model=ProcessResultModel)
def run_process(sandbox_id: str, body: ProcessRequestModel, request: Request):
    """Run one process with the shared contract. Clients never replay it."""
    try:
        process = body.to_request()
    except ValueError as exc:
        raise ControlError(422, "INVALID_REQUEST", str(exc)) from exc
    with _registry(request).use(sandbox_id) as handle:
        lease = request.app.state.manager.language_pools[handle.language].config.running_timeout
        if process.timeout > lease:
            raise ControlError(422, "INVALID_REQUEST", f"timeout exceeds the {lease}s sandbox lease")
        try:
            result = handle.sandbox.run_process(process)
        except Exception as exc:
            raise _sandbox_error(exc) from exc
    return ProcessResultModel.from_result(result)


@router.get("/sandboxes/{sandbox_id}/files", response_model=ExtractedFileResponse)
def extract_file(sandbox_id: str, request: Request, path: str = Query(max_length=4096),
                 max_bytes: int = Query(default=MAX_ARTIFACT_BYTES, ge=1, le=MAX_ARTIFACT_BYTES)):
    with _registry(request).use(sandbox_id) as handle:
        try:
            extracted = handle.sandbox.extract_file(path=path, max_bytes=max_bytes)
        except FileNotFoundError as exc:
            raise ControlError(status.HTTP_404_NOT_FOUND, "ARTIFACT_NOT_FOUND", "Artifact not found.") from exc
        except ArtifactReadError as exc:
            logger.error("Artifact readback failed: %s", exc, exc_info=True)
            raise ControlError(status.HTTP_500_INTERNAL_SERVER_ERROR, "ARTIFACT_READ_FAILED",
                               "The artifact exists but could not be read back.") from exc
        except (ArtifactTooLargeError, ValueError) as exc:
            raise ControlError(422, "ARTIFACT_INVALID", str(exc)) from exc
        except Exception as exc:
            raise _sandbox_error(exc) from exc
    return ExtractedFileResponse(path=extracted.path,
                                 content_bytes=base64.b64encode(extracted.content_bytes).decode("ascii"),
                                 size=extracted.size, content_text=extracted.content_text,
                                 encoding=extracted.encoding)


@router.delete("/sandboxes/{sandbox_id}", response_model=DisposeResponse)
def dispose_sandbox(sandbox_id: str, request: Request):
    result = _registry(request).close(sandbox_id)
    code = status.HTTP_202_ACCEPTED if result == DisposalStatus.CLOSING.value else status.HTTP_200_OK
    return JSONResponse(status_code=code, content={"status": result})


@router.get("/stats")
def get_stats(request: Request):
    manager = request.app.state.manager
    return {"pools": manager.get_pool_stats(), "budget": manager.get_budget_stats(),
            "handles": _registry(request).stats()}


def _default_manager():
    from sandbox_manager.manager import SandboxManager
    from sandbox_manager.models.pool_config import SandboxHostConfig
    return SandboxManager.from_config(
        SandboxHostConfig.load_from_yaml(os.getenv("SANDBOX_CONFIG_FILE", "sandbox_config.yml")))


def create_app(settings: Optional[ControlSettings] = None,
               manager_factory: Optional[Callable[[], object]] = None,
               clock: Callable[[], float] = time.monotonic) -> FastAPI:
    """Build the control API. The lifespan owns the manager and the handle reaper."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        control = settings or ControlSettings.from_env()
        control.validate()
        application.state.control = control
        manager = (manager_factory or _default_manager)()
        stop = threading.Event()
        reaper = None
        try:
            registry = HandleRegistry(manager, ttl=control.handle_ttl_seconds,
                                      tombstone_ttl=control.tombstone_seconds,
                                      max_tombstones=control.max_tombstones, clock=clock)
            application.state.manager = manager
            application.state.registry = registry
            application.state.acquire_limiter = anyio.CapacityLimiter(ACQUIRE_THREADS)
            reaper = threading.Thread(target=registry.run_reaper, name="sandbox-handle-reaper",
                                      args=(stop, control.reaper_interval_seconds), daemon=True)
            reaper.start()
            yield
        finally:
            stop.set()
            if reaper is not None:
                reaper.join(timeout=60)
            if getattr(application.state, "registry", None) is not None:
                application.state.registry.forget_all()
            manager.shutdown()

    application = FastAPI(title="Sandbox Manager API",
                          description="Private control API for sandbox containers",
                          version="2.0.0", lifespan=lifespan)
    application.add_middleware(BodyLimitMiddleware)

    @application.exception_handler(ControlError)
    async def control_error(_request: Request, exc: ControlError):
        return _error_response(exc.status_code, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Never echo request input (it may contain source code or fixtures).
        errors = [{"loc": list(item.get("loc", ())), "msg": item.get("msg", "")} for item in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": {
            "code": "INVALID_REQUEST", "message": "Request validation failed.", "errors": errors}})

    @application.get("/health")
    def health():
        """Liveness only; reveals nothing and needs no token."""
        return {"status": "ok"}

    application.include_router(router)
    return application


app = create_app()
