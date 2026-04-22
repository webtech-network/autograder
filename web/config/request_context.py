"""Per-request context helpers for structured logging."""

from contextvars import ContextVar


REQUEST_ID_HEADER = "X-Request-ID"
_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    """Store the request id for the active async context."""
    _request_id_ctx_var.set(request_id)


def get_request_id() -> str | None:
    """Get the request id from the active async context."""
    return _request_id_ctx_var.get()


def clear_request_id() -> None:
    """Clear request context after request completion."""
    _request_id_ctx_var.set(None)
