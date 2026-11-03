"""Sandbox lifecycle results and errors shared by local pools and the remote client.

Every error is a ``RuntimeError`` so the grading engine classifies it as an
execution-environment failure, never as a missing student artifact.
"""
from enum import Enum


class Disposal(Enum):
    """Defined result of disposing a leased sandbox."""
    DISPOSED = "disposed"                # this call confirmed destruction
    ALREADY_DISPOSED = "already_disposed"  # an earlier call or lease expiry confirmed it


class SandboxError(RuntimeError):
    """Base class for sandbox infrastructure failures."""


class SandboxCapacityError(SandboxError):
    """No sandbox could be leased: the pool is at its scale limit or shut down."""


class RuntimeUnavailableError(SandboxError):
    """This host has no runtime profile (image) for the requested language.

    The language may be valid and allowed by the definition; the host simply
    cannot execute it. Callers report a capability failure, never an invalid language.
    """


class SandboxCleanupError(SandboxError):
    """Disposal was not confirmed. The owner retains the record and retries it."""


class SandboxHandleError(SandboxError):
    """A remote lease handle is unknown (``sandbox_not_found``) or expired (``sandbox_expired``)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SandboxTransportError(SandboxError):
    """The control service could not be reached or failed to perform an operation."""

    def __init__(self, message: str, code: str = "transport_error"):
        super().__init__(message)
        self.code = code


class ArtifactTooLargeError(ValueError):
    """A requested artifact exceeds the caller's byte limit."""
