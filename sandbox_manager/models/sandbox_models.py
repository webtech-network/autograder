from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict
import requests


class Language(Enum):
    PYTHON = ("python", "sandbox-py:latest")
    JAVA = ("java", "sandbox-java:latest")
    NODE = ("node", "sandbox-node:latest")
    CPP = ("cpp", "sandbox-cpp:latest")

    def __new__(cls, value, image):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.image = image
        return obj

class SandboxState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"


@dataclass
class CommandResponse:
    """Response from executing a command in a sandbox container."""
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float  # in seconds

    @property
    def output(self) -> str:
        """Combined stdout for backward compatibility."""
        return self.stdout

    def __str__(self):
        return self.stdout


class HttpResponse:
    """Wrapper for HTTP responses from containerized applications."""

    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)

    def json(self) -> Any:
        """Parse response body as JSON."""
        return self._response.json()

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def ok(self) -> bool:
        return self._response.ok

    def __repr__(self):
        return f"<HttpResponse [{self.status_code}]>"


