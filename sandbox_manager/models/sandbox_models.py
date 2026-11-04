from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict
import requests


class SandboxState(Enum):
    """Lifecycle: idle -> active -> closing -> (disposed | quarantined).

    A used sandbox is never returned to the pool. ``quarantined`` means Docker
    did not confirm removal; the pool keeps tracking it and retries disposal.
    """
    IDLE = "idle"
    ACTIVE = "active"
    CLOSING = "closing"
    QUARANTINED = "quarantined"
    DISPOSED = "disposed"


class DisposalStatus(Enum):
    """Defined result of disposing a sandbox; repeated disposal is safe."""
    DISPOSED = "disposed"                  # Docker confirmed removal by this call.
    ALREADY_DISPOSED = "already_disposed"  # Removal was confirmed earlier.
    CLOSING = "closing"                    # Another caller is disposing it now.
    QUARANTINED = "quarantined"            # Removal failed; retained for bounded retry.

@dataclass
class ExtractedFile:
    """Result of extracting a single file from a sandbox container."""
    path: str
    content_bytes: bytes
    size: int
    content_text: str = ""
    encoding: str = "utf-8"


class HttpResponse:
    """Wrapper for HTTP responses from containerized applications."""

    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def status_code(self) -> int:
        """Returns the HTTP status code."""
        return self._response.status_code

    @property
    def text(self) -> str:
        """Returns the response body as text."""
        return self._response.text

    @property
    def headers(self) -> Dict[str, str]:
        """Returns the response headers."""
        return dict(self._response.headers)

    def json(self) -> Any:
        """Parse response body as JSON."""
        return self._response.json()

    @property
    def content(self) -> bytes:
        """Returns the response body as bytes."""
        return self._response.content

    @property
    def ok(self) -> bool:
        """Returns True if status_code is less than 400."""
        return self._response.ok

    def __repr__(self):
        return f"<HttpResponse [{self.status_code}]>"


