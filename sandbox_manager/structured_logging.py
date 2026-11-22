"""Structured logs shared by the API and the sandbox manager (one schema, #487).

Both services write one line per record to stdout: JSON when ``json_logs`` is on,
otherwise a human-readable line. Every line carries ``service``, ``env`` and the
active ``request_id``; ``trace_id``/``span_id`` appear only while a span is active
(#489), and ``attempt_id`` only inside a grading attempt.

What never reaches a log line: the raw request path or query string (sandbox
handle IDs are bearer-like capabilities, user IDs identify students), the client
address, and request headers. ``request_logging_middleware`` logs the matched
route *template* instead, and Uvicorn's own access line is silenced, and
libraries that dump requests (URLs, bodies, signed headers) log warnings only.
"""
import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional
from uuid import uuid4

from sandbox_manager.tracing import current_trace_ids, server_route

REQUEST_ID_HEADER = "X-Request-ID"
#: An incoming ``X-Request-ID`` is client-controlled: anything else is replaced.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
#: Record attributes copied into JSON lines when present.
CONTEXT_FIELDS = ("request_id", "attempt_id", "trace_id", "span_id", "method", "path", "status", "duration_ms")

#: Libraries whose INFO/DEBUG lines dump requests: URLs (a sandbox URL holds its
#: handle), bodies (the AI SDK logs the prompts, i.e. student code) or signed
#: headers (botocore logs the access key id and session token).
REQUEST_DUMPING_LOGGERS = ("urllib3", "httpx", "httpcore", "openai", "botocore", "boto3", "s3transfer")

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_attempt_id: ContextVar[Optional[str]] = ContextVar("attempt_id", default=None)
#: Request lines have the same logger name in both services; ``service`` tells them apart.
logger = logging.getLogger("http.request")


def get_request_id() -> Optional[str]:
    """The request id of the active context, if any."""
    return _request_id.get()


def set_request_id(request_id: Optional[str]) -> Token:
    """Bind ``request_id`` to the active context; pass the token to ``reset_request_id``."""
    return _request_id.set(request_id)


def reset_request_id(token: Token) -> None:
    """Restore the request id bound before ``set_request_id`` returned ``token``."""
    _request_id.reset(token)


def get_attempt_id() -> Optional[str]:
    """The grading attempt id of the active context, if any."""
    return _attempt_id.get()


def set_attempt_id(attempt_id: Optional[str]) -> Token:
    """Bind the grading attempt id to the active context; pass the token to ``reset_attempt_id``."""
    return _attempt_id.set(attempt_id)


def reset_attempt_id(token: Token) -> None:
    """Restore the attempt id bound before ``set_attempt_id`` returned ``token``."""
    _attempt_id.reset(token)


def accept_request_id(value: Optional[str]) -> str:
    """``value`` when it is a well-formed request id, otherwise a fresh one."""
    value = (value or "").strip()
    return value if REQUEST_ID_PATTERN.fullmatch(value) else uuid4().hex


class JSONFormatter(logging.Formatter):
    """One JSON object per record."""

    def __init__(self, service_name: str, app_env: str):
        super().__init__()
        self._service_name = service_name
        self._app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service_name,
            "env": self._app_env,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        for name in CONTEXT_FIELDS:
            value = getattr(record, name, None)
            if value is not None and value != "":
                log_data[name] = value
        return json.dumps(log_data, default=str)


class RequestContextFilter(logging.Filter):
    """Stamp the active request id (``-`` outside a request), attempt id and span ids on every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.attempt_id = get_attempt_id()
        record.trace_id, record.span_id = current_trace_ids()
        return True


class TextFormatter(logging.Formatter):
    """The human-readable line; it names the trace while a span is active."""

    def __init__(self):
        super().__init__("%(asctime)s - %(name)s - %(levelname)s - [request_id=%(request_id)s%(trace)s] %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "trace_id", None)
        record.trace = f" trace_id={trace_id}" if trace_id else ""
        return super().format(record)


class _ServiceHandler(logging.StreamHandler):
    """The stdout handler ``setup_logging`` owns (and replaces when called again)."""


def setup_logging(*, json_logs: bool, service_name: str, app_env: str, log_level: str = "INFO") -> None:
    """Send every log record of this process through one stdout handler.

    Uvicorn's error logs propagate to it; Uvicorn's access line (client address,
    raw path and query) is disabled in favour of ``request_logging_middleware``.
    Handlers installed by others (test log capture) are left in place.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    for handler in [h for h in root.handlers if isinstance(h, _ServiceHandler)]:
        root.removeHandler(handler)
    handler = _ServiceHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JSONFormatter(service_name, app_env) if json_logs else TextFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)
    # Even at LOG_LEVEL=DEBUG these libraries log warnings only.
    for name in REQUEST_DUMPING_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True


#: Routes whose successful (status < 400) responses are logged at DEBUG; others stay at INFO.
QUIET_ROUTES = frozenset({"/metrics"})


async def request_logging_middleware(request, call_next):
    """Bind the request id, echo it, and log one line per request.

    Register with ``app.middleware("http")(request_logging_middleware)``.
    """
    request_id = accept_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = set_request_id(request_id)
    start = perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("http_request_failed", extra={
                "method": request.method, "path": server_route(request.scope), "status": 500,
                "duration_ms": int((perf_counter() - start) * 1000)})
            raise
        response.headers[REQUEST_ID_HEADER] = request_id
        path = server_route(request.scope)
        # Prometheus scrapes /metrics every few seconds: its successful lines are DEBUG, not INFO.
        quiet = path in QUIET_ROUTES and response.status_code < 400
        logger.log(logging.DEBUG if quiet else logging.INFO, "http_request_completed", extra={
            "method": request.method, "path": path, "status": response.status_code,
            "duration_ms": int((perf_counter() - start) * 1000)})
        return response
    finally:
        reset_request_id(token)
