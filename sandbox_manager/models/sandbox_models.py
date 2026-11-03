from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict
import requests


class SandboxState(Enum):
    """Current state of a sandbox instance."""
    IDLE = "idle"          # warm, owned by the pool
    BUSY = "busy"          # leased to one session
    CLOSING = "closing"    # disposal started; owner retains the record until confirmed
    STOPPED = "stopped"    # destruction confirmed

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


